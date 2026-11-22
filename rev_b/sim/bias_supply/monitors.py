#!/usr/bin/env python3
"""BIAS_OK monitors as drawn on sheet 02 of the power amp rev B (second pass, 2026-11-23), and the
BIAS_EN pump with the control board's real driver.

The master's simulation (bias.py, run_vnc_monitor.py) has the two monitors as behavioural
comparators. Here they are the drawn circuit:

  VREF10 = LM4040A-10 fed by 1.0k from +15 V;  VREF5 = VREF10 / 2 (10k / 10k, 0.1 %)
  VNC monitor   VNC -- 169k + 234k -- MV -- 29.4k -- VREF10;  MV -- 3.57M -- OV;  10 nF;  BAV199 clamp
                LM2901B unit A: + MV, - VREF5; OV open (fault) when VNC is less negative than -63.0 V
  rail monitor  M80 -- 271k -- MR -- 16.9k -- VREF10;  MR -- 7.32M -- OR;  10 nF;  BAV199 clamp
                unit B: + MR, - VREF5; fault when the rail is less negative than -75.0 V
  +15 V monitor +15V -- 42.2k -- P15S -- 10k -- GND;  VREF2V5 -- 10k -- PREF -- 2.37M -- O15
                unit C: + PREF, - P15S; fault when +15 V is below 13.0 V (the LM4040 is still in
                regulation there: it needs about 11.5 V)
  OV, OR, O15: 10k pull-ups to +15 V; 1N4148W diode-OR into MON_FAULT (100k to GND), which drives
  the four channels' monitor clamps.  Unit D: + VREF5, - MON_FAULT; open = OK -> 22k to +15 V /
  10k to GND = BIAS_OK_A (4.5-4.9 V; no +15 V = not OK).

Comparator model: LM2901B, open collector, offset and bias current as parameters (data sheet
limits), about 1 us response, output off when its supply is below 2 V. Generic, not a vendor model.

Runs (results/monitors.md):
 1. thresholds over tolerance (analytic, every resistor / reference / offset term, 0-85 C), and
    the nominal trip / release points from a slow ngspice sweep of the drawn circuit;
 2. start-up with the rails in different orders and ramps: BIAS_OK must not go high while VNC,
    the rail or +15 V is outside its window;
 3. -80 V source lost with the HV on (four channels, the board's 100 uF): time to BIAS_OK low and
    the bias drift, against the master's behavioural figures (22-117 ms, 0 V typical);
 4. -80 V current with the monitor and ADC dividers added;
 5. the BIAS_EN pump with the 74AHCT driver, 100 ohm on the card, 100 ohm crossing and a series
    resistor (0 / 470 / 1k) at 5 / 10 / 15 kHz: release time, time to cold, driver peak current.
Usage: python3 monitors.py
"""
import os
import sys

import numpy as np
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bias  # noqa: E402
from run_bias_supply import run, RES, OUT  # noqa: E402

# ------------------------------------------------------------------ drawn values
V = dict(rref=1.0e3,
         ra_v=169e3 + 234e3, rb_v=29.4e3, rh_v=3.57e6,
         ra_r=271e3, rb_r=16.9e3, rh_r=7.32e6,
         ru15=42.2e3, rd15=10e3, rs15=10e3, rh15=2.37e6,
         rp=10e3, rmf=100e3, rok1=22e3, rok2=10e3, cmon=10e-9)
VL = 0.15            # comparator output low at about 1.5 mA
# tolerances (data sheet limits; see results)
TOL = dict(ref10=0.001, ref10_tc=100e-6,     # LM4040A10 (A grade 0.1 %), 100 ppm/K max
           r01=0.001, r01_tc=25e-6,           # 0.1 % thin film, 25 ppm/K
           r1=0.01, r1_tc=100e-6,             # 1 % (hysteresis, pull-ups)
           vos=5.5e-3, ib=50e-9,              # LM2901B: 5.5 mV over temperature, bias current 50 nA (out of the pin)
           v15=(14.4, 15.6), ref25=0.0002 + 2e-6 * 60)   # +15 V +-4 %; ADR4525B 0.02 %, 2 ppm/K
TEMPS = (0.0, 25.0, 85.0)

CMP = """
.subckt CMP inp inn out vcc gnd params: vos=0 ib=0
Ibp 0 inp DC {ib}
Ibn 0 inn DC {ib}
Bd d 0 V = {0.5*(1+tanh((V(inn)-V(inp)+vos)/0.2m)) * 0.5*(1+tanh((V(vcc,gnd)-2)/0.2))}
Rd d d2 1k
Cd d2 0 1n
Bo out gnd I = {V(d2) * 16m * tanh(V(out,gnd)/1.0) + 1n*V(out,gnd)}
Co out gnd 20p
.ends CMP
.model DSW D(is=2.5n rs=0.5 n=1.8 cjo=4p)
.model DLL D(is=5e-12 rs=2 n=1.9 cjo=2p)
.model DREF D(bv=9.965 ibv=1m rs=0.5 is=1e-14)
"""


def monitor(vos=(0, 0, 0, 0), ib=(0, 0, 0, 0), vcc='vcc', p5='p5', rail='raw', vnc='vnc'):
    """Netlist lines of the drawn monitor block. Nodes: uv = MON_FAULT (clamp gates), bias_ok =
    BIAS_OK_A; vref10, vref5, vr25 inside."""
    v = V
    L = [CMP,
         f'Rref {vcc} vref10 {v["rref"]}', 'Viz vref10 vrz 0', 'Dref 0 vrz DREF', 'Cref vref10 0 100n',
         'R5a vref10 vref5 10k', 'R5b vref5 0 10k', 'C5 vref5 0 100n',
         'Rvoc1 vref10 voc 39k', 'Rvoc2 voc 0 11k',                                   # over-current reference load
         f'Radc1 {vnc} adcv 909k', 'Radc2 adcv vref10 100k', f'Radc3 {rail} adcm 909k', 'Radc4 adcm vref10 100k',
         f'Bvr25 vr25 0 V = {{min(2.5, max(V({p5})-0.2, 0))}}',
         # VNC monitor
         f'Rav {vnc} mv {v["ra_v"]}', f'Rbv mv vref10 {v["rb_v"]}', f'Rhv mv ov {v["rh_v"]}', f'Cmv mv 0 {v["cmon"]}',
         'Dclv 0 mv DLL', f'XA mv vref5 ov {vcc} 0 CMP vos={vos[0]} ib={ib[0]}', f'Rpv {vcc} ov {v["rp"]}', 'Dov ov uv DSW',
         # rail monitor
         f'Rar {rail} mr {v["ra_r"]}', f'Rbr mr vref10 {v["rb_r"]}', f'Rhr mr orl {v["rh_r"]}', f'Cmr mr 0 {v["cmon"]}',
         'Dclr 0 mr DLL', f'XB mr vref5 orl {vcc} 0 CMP vos={vos[1]} ib={ib[1]}', f'Rpr {vcc} orl {v["rp"]}', 'Dor orl uv DSW',
         # +15 V monitor
         f'Ru15 {vcc} p15s {v["ru15"]}', f'Rd15 p15s 0 {v["rd15"]}', f'Rs15 vr25 pref {v["rs15"]}', f'Rh15 pref o15 {v["rh15"]}',
         f'XC pref p15s o15 {vcc} 0 CMP vos={vos[2]} ib={ib[2]}', f'Rp15 {vcc} o15 {v["rp"]}', 'Do15 o15 uv DSW',
         # MON_FAULT and BIAS_OK_A
         f'Rmf uv 0 {v["rmf"]}',
         f'XD vref5 uv okh {vcc} 0 CMP vos={vos[3]} ib={ib[3]}', f'Rok1 {vcc} okh {v["rok1"]}', f'Rok2 okh 0 {v["rok2"]}',
         'Rokx okh bias_ok 1k', 'Cokx bias_ok 0 100n']
    return '\n'.join(L)


def with_monitors(net, **kw):
    """Replace the master's behavioural monitors (Buv / Ruv / Cuv / Bok) by the drawn block."""
    keep = [ln for ln in net.split('\n') if not ln.startswith(('Buv', 'Ruv', 'Cuv', 'Bok'))]
    return '\n'.join(keep) + '\n' + monitor(**kw) + '\n'


# ------------------------------------------------------------------ 1. thresholds
def vout_high(rh, m, v15, rp, rd=100e3, others_high=0):
    """Comparator output high level: pull-up rp, loads rh to node m and the diode-OR pull-down."""
    return (v15 / rp + m / rh + 0.6 / rd) / (1 / rp + 1 / rh + 1 / rd)


def thr(ra, rb, rh, vref10, vref5, vo, ib, vos):
    """Vx at which the monitor node equals VREF5 + offset (bias current ib flows into the node)."""
    m = vref5 + vos
    return ra * (m * (1 / ra + 1 / rb + 1 / rh) - vref10 / rb - vo / rh - ib)


def thresholds(n=200000, seed=3):
    rng = np.random.default_rng(seed)
    u = lambda t, size=n: rng.uniform(-t, t, size)  # noqa: E731
    out = {}
    for name, ra, rb, rh in (('VNC', V['ra_v'], V['rb_v'], V['rh_v']), ('rail', V['ra_r'], V['rb_r'], V['rh_r'])):
        res = {}
        for T in TEMPS:
            dT = T - 25
            ref10 = 10 * (1 + u(TOL['ref10']) + u(TOL['ref10_tc']) * dT)
            ref5 = ref10 / 2 * (1 + u(TOL['r01'] + TOL['r01_tc'] * abs(dT)))
            ra_ = ra * (1 + u(TOL['r01']) + u(TOL['r01_tc']) * dT)
            rb_ = rb * (1 + u(TOL['r01']) + u(TOL['r01_tc']) * dT)
            rh_ = rh * (1 + u(TOL['r1']) + u(TOL['r1_tc']) * dT)
            rp_ = V['rp'] * (1 + u(TOL['r1']))
            v15 = rng.uniform(*TOL['v15'], n)
            ib = rng.uniform(0, TOL['ib'], n)
            vos = u(TOL['vos'])
            vl = rng.uniform(0.05, 0.25, n)
            trip = thr(ra_, rb_, rh_, ref10, ref5, vl, ib, vos)
            vh = vout_high(rh_, ref5, v15, rp_)
            rel = thr(ra_, rb_, rh_, ref10, ref5, vh, ib, vos)
            res[T] = (trip, rel)
        allt = np.concatenate([res[T][0] for T in TEMPS])
        allr = np.concatenate([res[T][1] for T in TEMPS])
        hy = np.concatenate([res[T][1] - res[T][0] for T in TEMPS])
        nom_vh = vout_high(rh, 5.0, 15.0, V['rp'])
        out[name] = dict(trip_nom=thr(ra, rb, rh, 10, 5, VL, 0, 0), rel_nom=thr(ra, rb, rh, 10, 5, nom_vh, 0, 0),
                         trip=(allt.min(), allt.max()), rel=(allr.min(), allr.max()), hyst=(hy.min(), hy.max()),
                         rel_T={T: (res[T][1].min(), res[T][1].max()) for T in TEMPS})
    # +15 V monitor
    r = V['rd15'] / (V['ru15'] + V['rd15'])
    res = []
    for T in TEMPS:
        dT = T - 25
        ref = 2.5 * (1 + u(TOL['ref25']))
        rr = r * (1 + u(2 * (TOL['r1'] + TOL['r1_tc'] * abs(dT))) * (1 - r))
        rs, rh = V['rs15'] * (1 + u(TOL['r1'])), V['rh15'] * (1 + u(TOL['r1']))
        vos, ib = u(TOL['vos']), rng.uniform(0, TOL['ib'], n)
        vl = rng.uniform(0.05, 0.25, n)
        pl = (ref / rs + vl / rh + ib) / (1 / rs + 1 / rh) + vos
        trip = pl / rr
        # release: output high; V15 at release is about 13.3 V
        vh = vout_high(rh + rs, 2.5, 13.3, V['rp'] * (1 + u(TOL['r1'])))
        ph = (ref / rs + vh / rh + ib) / (1 / rs + 1 / rh) + vos
        res.append((trip, ph / rr))
    t = np.concatenate([x[0] for x in res])
    rl = np.concatenate([x[1] for x in res])
    pl0 = (2.5 / V['rs15'] + VL / V['rh15']) / (1 / V['rs15'] + 1 / V['rh15'])
    ph0 = (2.5 / V['rs15'] + vout_high(V['rh15'] + V['rs15'], 2.5, 13.3, V['rp']) / V['rh15']) / (1 / V['rs15'] + 1 / V['rh15'])
    out['+15 V'] = dict(trip_nom=pl0 / r, rel_nom=ph0 / r, trip=(t.min(), t.max()), rel=(rl.min(), rl.max()),
                        hyst=((rl - t).min(), (rl - t).max()))
    return out


def sweep():
    """Slow sweeps of the drawn block alone: the VNC, rail and +15 V inputs one at a time."""
    rows = {}
    base = 'Vp5 p5 0 5\n'
    cases = {
        'VNC': ('Vvnc vnc 0 PWL(0 -70 1 -60 2 -70)\nVraw raw 0 -80\nVcc vcc 0 15', 'v(vnc)'),
        'rail': ('Vvnc vnc 0 -70\nVraw raw 0 PWL(0 -80 1 -72 2 -80)\nVcc vcc 0 15', 'v(raw)'),
        '+15 V': ('Vvnc vnc 0 -70\nVraw raw 0 -80\nVcc vcc 0 PWL(0 15 1 12 2 15)', 'v(vcc)'),
    }
    for name, (src, var) in cases.items():
        net = '* sweep\n.options method=gear reltol=1e-3 itl4=200\n' + bias.MODELS + '\n' + base + src + '\n' + monitor()
        _, f, out = run(net, f'tran 0.2m 2 0 0.2m\nwrdata sw.txt {var} v(uv) v(bias_ok)')
        d = f['sw.txt']
        t, x, uv, ok = d[:, 0], d[:, 1], d[:, 3], d[:, 5]
        up = (t < 1)
        trip = x[up][np.argmax(uv[up] > 5)] if (uv[up] > 5).any() else None
        dn = (t > 1)
        rel = x[dn][np.argmax(uv[dn] < 5)] if (uv[dn] < 5).any() else None
        rows[name] = (trip, rel, ok[t < 0.05].mean(), uv.max())
    return rows


# ------------------------------------------------------------------ 2. start-up
def startup(case):
    """Rails as PWL sources. Returns (t of BIAS_OK high, any 'illegal' high time, max illegal ok)."""
    srcs = {
        'together (master: -80 V 0-50 ms, +-15 V 10-30 ms, +5 V 0-20 ms)':
            ('PWL(0 0 0.05 -80)', 'PWL(0 0 0.01 0 0.03 15)', 'PWL(0 0 0.01 0 0.03 -15)', 'PWL(0 0 0.02 5)'),
        '-80 V 0.5 s after the low-voltage rails':
            ('PWL(0 0 0.5 0 0.55 -80)', 'PWL(0 0 0.02 15)', 'PWL(0 0 0.02 -15)', 'PWL(0 0 0.02 5)'),
        '+-15 V 0.5 s after -80 V':
            ('PWL(0 0 0.05 -80)', 'PWL(0 0 0.5 0 0.52 15)', 'PWL(0 0 0.5 0 0.52 -15)', 'PWL(0 0 0.02 5)'),
        '+5 V 0.5 s after the others':
            ('PWL(0 0 0.05 -80)', 'PWL(0 0 0.02 15)', 'PWL(0 0 0.02 -15)', 'PWL(0 0 0.5 0 0.52 5)'),
        '+-15 V ramping slowly (1 s), -80 V first':
            ('PWL(0 0 0.05 -80)', 'PWL(0 0 0.1 0 1.1 15)', 'PWL(0 0 0.1 0 1.1 -15)', 'PWL(0 0 0.02 5)'),
        '-80 V ramping slowly (1 s), low-voltage rails first':
            ('PWL(0 0 0.1 0 1.1 -80)', 'PWL(0 0 0.02 15)', 'PWL(0 0 0.02 -15)', 'PWL(0 0 0.02 5)'),
    }
    raw, vcc, vee, p5 = srcs[case]
    net = bias.netlist({}, dac='DC 0', raw_src=f'Vraw raw 0 {raw}', vcc_src=f'Vcc vcc 0 {vcc}',
                       vee_src=f'Vee vee 0 {vee}', en='force', nch=4)
    net = with_monitors(net) + f'Vp5 p5 0 {p5}\n'
    _, f, out = run(net, 'tran 0.2m 2.0 0 0.2m\nwrdata su.txt v(bias_ok) v(vnc) v(raw) v(vcc) v(bias1) v(uv)')
    d = f['su.txt']
    t, ok, vnc, raw_, vc, b1, uv = (d[:, i] for i in (0, 1, 3, 5, 7, 9, 11))
    legal = (vnc < -63.0) & (raw_ < -75.0) & (vc > 12.9)
    hi = ok > 2.0
    bad = hi & ~legal
    first = t[np.argmax(hi)] if hi.any() else None
    return dict(t_ok=first, bad_ms=bad.sum() * 0.2, bad_max=ok[~legal].max() if (~legal).any() else 0,
                hot=b1[(t > 0.005) & (uv < 5)].max() if ((t > 0.005) & (uv < 5)).any() else None,
                t_legal=t[np.argmax(legal)] if legal.any() else None)


# ------------------------------------------------------------------ 3. -80 V lost
def lost(dac):
    raw = ('Vrs rs 0 PWL(0 0 0.05 -80)\nRrs rs rsw 10\nSoff rsw raw ctl 0 SOFF\n.model SOFF SW(vt=0.5 ron=0.1 roff=1e9)\n'
           'Vctl ctl 0 PWL(0 1 1.0 1 1.0001 0)\nChold raw 0 100u')
    net = bias.netlist({}, dac=f'DC {dac}', raw_src=raw, vcc_src='Vcc vcc 0 PWL(0 0 0.01 0 0.03 15)',
                       vee_src='Vee vee 0 PWL(0 0 0.01 0 0.03 -15)', en='force', nch=4)
    net = with_monitors(net) + 'Vp5 p5 0 5\n'
    _, f, out = run(net, 'tran 0.2m 2.0 0 0.2m\nwrdata pw.txt v(bias1) v(bias_ok) v(vnc) v(raw)')
    d = f['pw.txt']
    t, vb, ok = d[:, 0], d[:, 1], d[:, 3]
    pre = (t > 0.9) & (t < 1.0)
    if ok[pre].min() < 2.0:
        return dict(ms=None)
    inh = (t > 1.0) & (ok < 2.0)
    ti = t[np.argmax(inh)]
    win = (t >= 1.0) & (t <= ti + 0.001)
    return dict(ms=(ti - 1.0) * 1e3, before=vb[pre].mean(), drift=vb[win].max() - vb[pre].mean())


# ------------------------------------------------------------------ 4. -80 V current
def rail_current(dac):
    net = bias.netlist({}, dac=f'DC {dac}', en='force', nch=4)
    net = with_monitors(net) + 'Vp5 p5 0 5\n'
    _, f, out = run(net, 'tran 1m 1.2 1.1 1m\nwrdata rc.txt v(bias1) i(Vraw) i(Vcc) v(vref10) i(Viz)')
    d = f['rc.txt'][-1]
    return d[1], abs(d[3]) * 1e3, abs(d[5]) * 1e3, d[7], abs(d[9]) * 1e3


# ------------------------------------------------------------------ 5. BIAS_EN pump
def pump(rs, freq, vto=1.0):
    """BIAS_EN from the card's 74AHCT (5 V, about 50 ohm at 8 mA) + 100 ohm at the card + the 100 ohm
    crossing + rs, into the 100 nF / BAT54S pump. Toggling from 0.1 s, stopped high at 0.6 s (run A)
    or low (run B). Returns release time (ms, CLAMP_WD below 1 V), cold time after the stop (ms, the
    channel's bias below -60 V), pump node peak current (mA)."""
    res = []
    for stop_level in (5, 0):
        half = 0.5 / freq
        src = (f'Ven0 en0 0 PULSE(0 5 0.1 20n 20n {half - 20e-9} {2 * half})\n'
               f'Ben en 0 V = {{time < 0.6 ? V(en0) : {stop_level}}}\n'
               f'Rdrv en en1 50\nRcard en1 en2 100\nRx en2 bias_en_a 100\nRpd bias_en_a 0 100k\nVis bias_en_a en3a 0\nRs en3a en3 {rs or 0.001}\n')
        net = bias.netlist({}, dac='DC 1.25', en='DC 0', nch=1).replace('Rst wst 0 100k', 'Rst wst 0 56k')
        # replace the master's watchdog front end by the drawn one (BAT54S pump, 2N7002 with vto)
        lines = [ln for ln in net.split('\n') if not ln.startswith(('Ven ', 'Cwd', 'Dwd1', 'Dwd2', 'Mqen'))]
        net = '\n'.join(lines) + '\n' + src + ('Cwd en3 wp 100n\nDwd1 0 wp DSCH\nDwd2 wp wst DSCH\n'
                                               f'Mqen cg wst 0 0 NWD\n.model NWD NMOS(level=1 vto={vto} kp=50m)\n'
                                               '.model DSCH D(is=1u rs=2 n=1.05 cjo=10p)\n')
        _, f, out = run(net, 'tran 2u 1.0 0 2u\nwrdata pu.txt v(cg) v(bias1) i(Vis)')
        d = f['pu.txt']
        t, cg, b1, i = d[:, 0], d[:, 1], d[:, 3], d[:, 5]
        on = (t > 0.1) & (cg < 1.0)
        rel = (t[np.argmax(on)] - 0.1) * 1e3 if on.any() else None
        cold = (t > 0.6) & (b1 < -60)
        cms = (t[np.argmax(cold)] - 0.6) * 1e3 if cold.any() else None
        res.append((rel, cms, np.abs(i[(t > 0.1) & (t < 0.6)]).max() * 1e3, cg[(t > 0.5) & (t < 0.6)].max()))
    return res


def main():
    os.makedirs(RES, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    L = ['# BIAS_OK monitors as drawn, and the BIAS_EN pump\n',
         '> Generated by `monitors.py` (power amp rev B, second pass); do not edit. ngspice-47, generic models;',
         '> the comparators are a behavioural LM2901B (open collector, data sheet offset / bias current), the',
         '> bias channels are the master\'s bias.py (72 V string, typical board).\n',
         '## 1. Thresholds\n',
         'Tolerances: LM4040A10 0.1 % + 100 ppm/K; dividers 0.1 %, 25 ppm/K; hysteresis resistors and pull-ups 1 %; '
         'LM2901B offset ±5.5 mV, bias current 0-50 nA out of the pin; +15 V 14.4-15.6 V; output low 0.05-0.25 V; '
         f'local temperature {", ".join(f"{t:.0f}" for t in TEMPS)} °C (the reference end of the board is taken as 70 °C air + up to 15 K). '
         '200 000 Monte Carlo boards per temperature, uniform distributions, extremes reported (this is a worst-case range, '
         'not 3 sigma).\n',
         '| Monitor | Trip, nominal (V) | Trip, range | Release, nominal | Release, range | Hysteresis, range | Target (bias_supply.md) |',
         '|---|---|---|---|---|---|---|']
    th = thresholds()
    tgt = {'VNC': 'trip -63.0 (-62.2 to -63.8), release -64.5, worst release above -65.4 (weakest VNC -66.4 + 1.0 V)',
           'rail': 'trip -75.0 (-74.1 to -75.9), release -75.5 (worst -76.4), below the lowest rail -77.8',
           '+15 V': 'new: +15 V present; trip 13.0 V, release 13.3 V (VREF10 needs about 11.5 V)'}
    for k, r in th.items():
        L.append(f'| {k} | {r["trip_nom"]:.2f} | {r["trip"][0]:.2f} to {r["trip"][1]:.2f} | {r["rel_nom"]:.2f} | '
                 f'{r["rel"][0]:.2f} to {r["rel"][1]:.2f} | {r["hyst"][0]:.2f} to {r["hyst"][1]:.2f} | {tgt[k]} |')
    L += ['', 'Release range by local temperature (the weakest VNC, -66.4 V, is a cold board: VNC grows more negative '
          'when hot, by the zeners\' positive temperature coefficient):\n', '| Monitor | ' + ' | '.join(f'{t:.0f} °C' for t in TEMPS) + ' |',
          '|---|' + '---|' * len(TEMPS)]
    for k in ('VNC', 'rail'):
        L.append(f'| {k} | ' + ' | '.join(f'{th[k]["rel_T"][t][0]:.2f} to {th[k]["rel_T"][t][1]:.2f}' for t in TEMPS) + ' |')
    sw = sweep()
    L += ['', 'Nominal parts, slow ngspice sweep of the drawn block (input up and back down over 1 s each):\n',
          '| Input swept | Trip (V) | Release (V) | BIAS_OK_A while OK (V) | MON_FAULT high (V) |', '|---|---|---|---|---|']
    for k, (t, r, ok, uvm) in sw.items():
        L.append(f'| {k} | {t:.2f} | {r:.2f} | {ok:.2f} | {uvm:.2f} |')
    L += ['', '## 2. Start-up\n',
          '"Illegal" = BIAS_OK_A above 2 V while VNC is above -63 V, the rail above -75 V or +15 V below 12.9 V. '
          'All channels at DAC 0, typical board.\n',
          '| Rails | BIAS_OK high at (s) | all three conditions met at (s) | time illegal (ms) | highest BIAS_OK while illegal (V) |',
          '|---|---|---|---|---|']
    cases = ('together (master: -80 V 0-50 ms, +-15 V 10-30 ms, +5 V 0-20 ms)', '-80 V 0.5 s after the low-voltage rails',
                 '+-15 V 0.5 s after -80 V', '+5 V 0.5 s after the others', '+-15 V ramping slowly (1 s), -80 V first',
                 '-80 V ramping slowly (1 s), low-voltage rails first')
    pool = Pool()
    sus = pool.map(startup, cases)
    for case, s in zip(cases, sus):
        L.append(f'| {case} | {s["t_ok"] if s["t_ok"] is None else round(s["t_ok"], 3)} | '
                 f'{s["t_legal"] if s["t_legal"] is None else round(s["t_legal"], 3)} | {s["bad_ms"]:.1f} | {s["bad_max"]:.2f} |')
    L += ['', '## 3. -80 V source lost with the HV on\n',
          'Four channels at the same code, the board\'s 100 µF only, ±15 V up. Master (behavioural monitors): 22-117 ms, '
          '0 V drift on a typical board.\n',
          '| DAC (V) | bias before (V) | BIAS_OK low after (ms) | bias drift before that (V) |', '|---|---|---|---|']
    for dac, r in zip((0.5, 1.0, 1.36, 2.0), pool.map(lost, (0.5, 1.0, 1.36, 2.0))):
        L.append(f'| {dac} | {r.get("before", float("nan")):.1f} | {r["ms"] if r["ms"] is None else round(r["ms"])} | '
                 f'{r.get("drift", float("nan")):.2f} |')
    L += ['', '## 4. -80 V and +15 V current with the monitor and ADC dividers\n',
          '| DAC (V) | bias (V) | -80 V (mA) | +15 V, bias circuit + monitors (mA) | VREF10 (V) | LM4040 current (mA) |',
          '|---|---|---|---|---|---|']
    for dac in (0.0, 1.36, 2.5):
        b, im80, i15, vr, iz = rail_current(dac)
        L.append(f'| {dac} | {b:.1f} | {im80:.2f} | {i15:.2f} | {vr:.3f} | {iz:.2f} |')
    L += ['', '## 5. BIAS_EN pump with the card\'s driver\n',
          'Driver: 74AHCT1G (5 V, modelled as 50 Ω), 100 Ω at the card, the 100 Ω crossing (R513) and the new series '
          'resistor; 100 nF, BAT54S, 1 µF ‖ 56k (was 100k: with a 5 V drive the pump charges higher and the cold time grew to 200 ms), 2N7002 (Vgs(th) as given), CLAMP_WD pulled up by 100k. One channel at '
          'DAC 1.25 V. The control board asked for ≥ 470 Ω (74AHCT: 8 mA rated, 25 mA absolute).\n',
          '| Series R | f (kHz) | 2N7002 Vgs(th) (V) | release (ms) | cold after stop high (ms) | cold after stop low (ms) | driver peak (mA) | CLAMP_WD while running (V) |',
          '|---|---|---|---|---|---|---|---|']
    jobs = [(rs, fk, vto) for rs in (0, 470, 1000) for fk in (5, 10, 15) for vto in ((1.0, 2.5) if rs == 1000 else (1.0,))]
    for (rs, fk, vto), ((r1, c1, i1, cg1), (r2, c2, i2, cg2)) in zip(jobs, pool.starmap(pump, [(a, b * 1e3, c) for a, b, c in jobs])):
                L.append(f'| {rs} | {fk} | {vto} | {r1 if r1 is None else round(r1, 1)} | {c1 if c1 is None else round(c1)} | '
                         f'{c2 if c2 is None else round(c2)} | {max(i1, i2):.1f} | {cg1:.2f} |')
    open(os.path.join(RES, 'monitors.md'), 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    main()
