#!/usr/bin/env python3
"""VNC reference and VNC monitor (BIAS_OK) over part tolerances, temperature and the -80 V rail
(review E2, M24). Circuit: bias.py, four channels.

1. VNC over corners and a Monte Carlo run: zener string tolerance and temperature coefficient,
   its dynamic resistance, the follower's Vgs(th) and gain, 1 % resistors, 0-70 C, the rail at
   -78 .. -82 V, all channels cold and all at the hot end.
2. The monitor's own tolerance (reference, divider, comparator offset), and from both the trip /
   release thresholds that every board passes.
3. "-80 V lost" with the HV still on: time to BIAS_OK low and how far the bias drifts hot before
   the clamp, for the typical board and the worst boards; the cathode current that gives in an
   EL34 and a KT88 (sim/models).
4. The -80 V current over the bias range.

Writes results/vnc_monitor.md. Usage: python3 run_vnc_monitor.py
"""
import itertools
import os
import sys
from multiprocessing import Pool

import numpy as np

import bias
from run_bias_supply import run, RES, OUT

LIB = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'models', 'tubes.lib'))
RAILS = (-82.0, -81.0, -80.0, -79.0, -78.0)
TEMPS = (0.0, 25.0, 70.0)
NMC = 400

# ---------------------------------------------------------------- part data
# Zener strings (BZX84-B, +-2 % at 2 mA). S_Z in mV/K for the string, (min, typ, max), and the
# dynamic resistance at 0.5-2 mA (typ .. max), from the BZX84 series table (to confirm against the
# data sheet of the part bought): B33 27.4 / 29.7 / 33.4, B36 30.4 / 33.0 / 37.4, B43 37.6 / 41.2 / 46.6.
S76, S72, SLT = '76 V (B33 + B43), Rz 3.9k', '72 V (2x B36), Rz 3.3k', '72 V low-TC reference (±1 %, ±50 ppm/K), Rz 3.3k'
STRINGS = {
    S76: dict(vz=76.0, tol=0.02, sz=(65.0, 70.9, 80.0), rz=3.9e3),      # as drawn (power amp rev B)
    S72: dict(vz=72.0, tol=0.02, sz=(60.8, 66.0, 74.8), rz=3.3e3),      # proposed
    SLT: dict(vz=72.0, tol=0.01, sz=(-3.6, 0.0, 3.6), rz=3.3e3),        # for comparison, not drawn
}
ZRS = (60.0, 150.0, 300.0)
# BSP92P: Vgs(th) -1.0 / -1.5 / -2.0 V at 130 uA, 25 C; about -3 mV/K (2-4) on |Vgs(th)|
VTO = (-1.0, -1.5, -2.0)
VTC = (2e-3, 3e-3, 4e-3)
KP = (0.25, 0.5, 1.0)
RTOL = 0.01
# monitor: LM4040-10 (0.5 %, 100 ppm/K), divider (two resistors), LM393 offset 9 mV over
# temperature referred to VNC through the divider (x 7.8)
REF_TOL = 0.005 + 100e-6 * 45
VOS = 0.009 * 7.8
MARGIN = 1.0      # V between the weakest board's VNC and the worst-case release threshold
HYST = 1.5        # V
RAIL_TRIP = -75.0
RAIL_HYST = 0.5
RAIL_MIN = -77.8  # -78 V at the tab less 0.2 V in the 10 ohm fusible resistor


def board(string, ztol=0.0, sz=1, zrs=1, vto=1, vtc=1, kp=1, rt=None):
    """A board: indices 0/1/2 pick min/typ/max, or give numbers directly (Monte Carlo)."""
    s = STRINGS[string]
    pick = lambda tab, x: tab[x] if isinstance(x, int) else x  # noqa: E731
    return dict(string=string, vz25=s['vz'] * (1 + ztol * s['tol']), sz=pick(s['sz'], sz) * 1e-3, zrs=pick(ZRS, zrs),
                vto25=pick(VTO, vto), vtc=pick(VTC, vtc), kp=pick(KP, kp), rz=s['rz'],
                rt=rt or {})


def params(b, temp):
    p = dict(vz=b['vz25'] + b['sz'] * (temp - 25), zrs=b['zrs'], kp=b['kp'], rz=b['rz'],
             vto=b['vto25'] + b['vtc'] * (temp - 25))      # |Vgs(th)| falls when hot
    for k, e in b['rt'].items():
        p[k] = (p.get(k) or bias.DEFAULTS[k]) * (1 + e)
    return p


def vnc_job(a):
    """DC sweep of the rail for one board, temperature and load. Returns per rail:
    VNC, zener current (A), -80 V current (A), bias (V)."""
    b, temp, dac = a
    p = dict(params(b, temp), uvlo=False)       # monitors out: the spread of VNC itself
    net = bias.netlist(p, dac=f'DC {dac}', en='force', nch=4)
    _, f, out = run(net, 'dc Vraw -82 -78 1\nwrdata v.txt v(vnc) v(zr) i(Vraw) v(bias1)')
    d = f.get('v.txt')
    if d is None or len(d) != 5:
        return None
    rz = p['rz']
    return np.column_stack([d[:, 1], (d[:, 3] - d[:, 0]) / rz, np.abs(d[:, 5]), d[:, 7]])


def spread(pool, string):
    """Corners (every combination of the extremes) and a Monte Carlo run. Returns arrays
    [board, temp, load, rail, quantity]."""
    corners = [board(string, z, s, r, v, c, k) for z, s, r, v, c, k in
               itertools.product((-1, 1), (0, 2), (0, 2), (0, 2), (0, 2), (0, 2))]
    rng = np.random.default_rng(1)
    mc = []
    for _ in range(NMC):
        u = lambda t: rng.uniform(t[0], t[2])  # noqa: E731
        mc.append(board(string, rng.uniform(-1, 1), u(STRINGS[string]['sz']), u(ZRS), -u([-x for x in VTO]),
                        u(VTC), u(KP), rt={k: rng.uniform(-RTOL, RTOL) for k in ('rz', 'rgv', 'rpdn', 'rf', 'rs', 'rpd')}))
    out = {}
    for name, boards in (('corners', corners), ('mc', mc)):
        jobs = [(b, t, dac) for b in boards for t in TEMPS for dac in (0.0, 2.5)]
        r = pool.map(vnc_job, jobs, chunksize=4)
        bad = sum(x is None for x in r)
        if bad:
            print(f'{string} {name}: {bad} runs failed', file=sys.stderr)
        r = [x if x is not None else np.full((5, 4), np.nan) for x in r]
        out[name] = np.array(r).reshape(len(boards), len(TEMPS), 2, 5, 4)
    return out


def monitor_tol(rtol):
    """Worst-case and Monte Carlo (3 sigma equivalent: 99.7 % range) error of the trip threshold,
    as a fraction of the threshold, plus the offset term in volts."""
    wc = REF_TOL + 2 * rtol
    rng = np.random.default_rng(2)
    n = 200000
    e = (1 + rng.uniform(-REF_TOL, REF_TOL, n)) * (1 + rng.uniform(-rtol, rtol, n)) / (1 + rng.uniform(-rtol, rtol, n)) - 1
    return wc, np.percentile(np.abs(e), 99.7)


def thresholds(weakest, rtol):
    """Release threshold: its worst case (most negative) stays MARGIN above the weakest board.
    Trip = release + HYST. Returns nominal release, nominal trip, and the trip's range."""
    wc, _ = monitor_tol(rtol)
    rel_worst = weakest + MARGIN                       # most negative release allowed
    rel = (rel_worst + VOS) / (1 + wc)                 # nominal
    rel = np.ceil(rel * 10) / 10                       # round toward 0 V (safe side for "passes")
    trip = rel + HYST
    return rel, trip, (trip * (1 + wc) - VOS, trip * (1 - wc) + VOS)


def lost_job(a):
    """-80 V source disconnected at 1.0 s with the board's 100 uF hold-up; +-15 V stay up.
    Returns ms to BIAS_OK low, bias before, hottest bias before BIAS_OK drops, VNC before,
    -80 V current before (mA), and when the clamped bias has followed the dying rail to -40 / -20 V."""
    b, temp, dac, trip, rail_trip = a
    p = dict(params(b, temp), uv_trip=trip, uv_hyst=HYST, rail_trip=rail_trip, rail_hyst=RAIL_HYST)
    raw = ('Vrs rs 0 PWL(0 0 0.05 -80)\nRrs rs rsw 10\nSoff rsw raw ctl 0 SOFF\n.model SOFF SW(vt=0.5 ron=0.1 roff=1e9)\n'
           'Vctl ctl 0 PWL(0 1 1.0 1 1.0001 0)\nChold raw 0 100u')
    net = bias.netlist(p, dac=f'DC {dac}', raw_src=raw, vcc_src='Vcc vcc 0 PWL(0 0 0.01 0 0.03 15)',
                       vee_src='Vee vee 0 PWL(0 0 0.01 0 0.03 -15)', en='force', nch=4)
    _, f, out = run(net, 'tran 0.2m 6.0 0 0.2m\nwrdata pw.txt v(bias1) v(bias_ok) v(vnc) i(Vrs) v(raw)')
    d = f.get('pw.txt')
    if d is None:
        return None
    t, vb, ok, vnc, irs = d[:, 0], d[:, 1], d[:, 3], d[:, 5], d[:, 7]
    pre = (t > 0.9) & (t < 1.0)
    if ok[pre].min() < 0.5:
        return dict(ms=None, note='BIAS_OK never came')
    inh = (t > 1.0) & (ok < 0.5)
    if not inh.any():
        return dict(ms=None, note='BIAS_OK did not drop')
    ii = np.argmax(inh)
    ti = t[ii]
    win = (t >= 1.0) & (t <= ti + 0.001)
    ic = ii + np.argmin(vb[ii:ii + 2500])          # coldest point after the clamp (within 0.5 s)

    def reach(level):
        m = vb[ic:] > level
        return (t[ic + np.argmax(m)] - 1.0) if m.any() else None
    return dict(ms=(ti - 1.0) * 1e3, before=vb[pre].mean(), hot=vb[win].max(), vnc=vnc[pre].mean(),
                ima=abs(irs[pre].mean()) * 1e3, cold=vb[ic], t40=reach(-40.0), t20=reach(-20.0))


# ---------------------------------------------------------------- tubes
TUBE_PTS = [  # tube, model, Pa max, V_ANODE, V_SCREEN (D13 setpoints; 400 V is PA-6's maximum)
    ('EL34', 'EL34_R', 25.0, 400.0, 370.0), ('EL34', 'EL34_R', 25.0, 250.0, 240.0),
    ('KT88', 'KT88_X', 42.0, 400.0, 320.0), ('KT88', 'KT88_X', 42.0, 250.0, 247.0),
]


def tube_curve(model, va, vs):
    """Static cathode current and plate dissipation against Vg1: plate through half the OT's DCR,
    screen through 1k, 1 ohm cathode shunt."""
    net = (f'* tube\n.include "{LIB}"\nVa vas 0 {va}\nRa vas a 23.5\nVs vss 0 {vs}\nRs vss s 1k\n'
           f'Vg g 0 0\nX1 a s g k {model}\nRk k 0 1\n.options itl1=500')
    _, f, out = run(net, 'dc Vg -90 0 0.25\nwrdata tc.txt v(k) v(a) i(Va)')
    d = f['tc.txt']
    return d[:, 0], d[:, 1], (d[:, 3] - d[:, 1]) * np.abs(d[:, 5])     # Vg1, Ik (A), Pa (W)


def fmt(x, n=1):
    return '–' if x is None or (isinstance(x, float) and np.isnan(x)) else f'{x:.{n}f}'


def main():
    os.makedirs(RES, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    L = ['# VNC reference and VNC monitor (BIAS_OK): tolerance run\n',
         '> Generated by `run_vnc_monitor.py`; do not edit. Circuit: bias.py, four channels, ngspice-47.',
         '> Generic device models with the parts\' data sheet spreads applied as parameters (below).\n',
         '## Part data used\n',
         '| Part | Spread |', '|---|---|',
         '| Zener string | ±2 % at 2 mA, 25 °C (BZX84-B). Temperature coefficient of the string: 76 V (B33 + B43, as drawn) '
         '65 / 70.9 / 80 mV/K; 72 V (2x B36) 60.8 / 66 / 74.8 mV/K (min / typ / max). Dynamic resistance of the string 60 / 150 / 300 Ω. For comparison (not drawn): a 72 V reference with ±1 % and ±50 ppm/K |',
         '| Followers | BSP92P, Vgs(th) -1.0 / -1.5 / -2.0 V at 25 °C, 2 / 3 / 4 mV/K smaller when hot; gain factor 0.25 / 0.5 / 1 A/V² |',
         '| Resistors | 1 % (Rz, 47k, 100k, Rf, the V-to-I 1k, the 22k pull-downs) in the Monte Carlo run |',
         '| Temperature | 0, 25, 70 °C (ENV-2: up to 70 °C under the top plate) |',
         '| -80 V rail at the board | -78 to -82 V (±2 V) and -79 to -81 V (±1 V); the 10 Ω fusible resistor takes another 0.03-0.2 V |',
         f'| Monitor | LM4040-10 (0.5 %, 100 ppm/K), divider of two resistors (1 % or 0.1 %), LM393 offset 9 mV ({VOS * 1e3:.0f} mV at VNC) |',
         '',
         f'Corners: all {2 ** 6} combinations of the extremes; Monte Carlo: {NMC} boards, uniform distributions. '
         'Each at 3 temperatures, all channels cold (DAC 0) and all at the hot end (DAC 2.5 V), 5 rail voltages.\n']
    with Pool() as pool:
        sp = {s: spread(pool, s) for s in STRINGS}
        chosen = {}
        # ---------------- VNC spread
        L += ['## VNC spread\n',
              'VNC = -(zener string) + |Vgs| of the followers. "Out of regulation": the string carries less than 50 µA, '
              'so VNC follows the rail (rail + |Vgs|) and not the string.\n',
              '| String | Rail | VNC corners (V) | VNC Monte Carlo (V) | Lowest string current, corners (mA) | Corner cases out of regulation | Monte Carlo cases out of regulation |',
              '|---|---|---|---|---|---|---|']
        for s in STRINGS:
            for sel, name in ( ((1, 2, 3), '-80 ±1 V'), ((0, 1, 2, 3, 4), '-80 ±2 V')):
                c = sp[s]['corners'][:, :, :, sel, :]
                m = sp[s]['mc'][:, :, :, sel, :]
                L.append(f'| {s} | {name} | {np.nanmin(c[..., 0]):.1f} to {np.nanmax(c[..., 0]):.1f} | {np.nanmin(m[..., 0]):.1f} to {np.nanmax(m[..., 0]):.1f} '
                         f'| {np.nanmin(c[..., 1]) * 1e3:.2f} | {100 * np.nanmean(c[..., 1] < 50e-6):.0f} % | {100 * np.nanmean(m[..., 1] < 50e-6):.0f} % |')
        L += ['', 'By temperature (corners, rail -80 ±2 V):\n', '| String | 0 °C | 25 °C | 70 °C | 70 °C: cases out of regulation at -78 / -79 / -80 V |', '|---|---|---|---|---|']
        for s in STRINGS:
            c = sp[s]['corners']
            L.append(f'| {s} | ' + ' | '.join(f'{np.nanmin(c[:, i, :, :, 0]):.1f} to {np.nanmax(c[:, i, :, :, 0]):.1f}' for i in range(3))
                     + ' | ' + ' / '.join(f'{100 * np.nanmean(c[:, 2, :, ri, 1] < 50e-6):.0f} %' for ri in (4, 3, 2)) + ' |')
        L += ['', 'What moves VNC (typical board, 76 V string, -80 V): '
              f'zener ±2 %: ±{0.02 * 76:.1f} V; zener temperature 0 → 70 °C: {-25 * 70.9e-3:+.1f} → {45 * 70.9e-3:+.1f} V on the string; '
              'Vgs(th) spread: ±0.5 V; load (cold → hot end, 3 → 19 mA): about 0.2 V.\n']
        # typical board
        typ = {s: pool.map(vnc_job, [(board(s), t, dac) for t in TEMPS for dac in (0.0, 2.5)]) for s in STRINGS}
        L += ['| String | Typical board, VNC at 0 / 25 / 70 °C, cold (V) | at the hot end (V) | bias at DAC 0 / full scale, 25 °C (V) |', '|---|---|---|---|']
        for s in STRINGS:
            r = typ[s]
            L.append(f'| {s} | ' + ' / '.join(f'{r[2 * i][2, 0]:.2f}' for i in range(3)) + ' | ' + ' / '.join(f'{r[2 * i + 1][2, 0]:.2f}' for i in range(3))
                     + f' | {r[2][2, 3]:.1f} / {r[3][2, 3]:.1f} |')
        L += ['', f'VNC step when the clamp removes the load (hot end → cold, typical board): {abs(typ[S72][3][2, 0] - typ[S72][2][2, 0]):.2f} V; the hysteresis must be larger than this.']
        # ---------------- thresholds
        wc1, mc1 = monitor_tol(0.01)
        wc01, mc01 = monitor_tol(0.001)
        L += ['', '## Monitor threshold\n',
              f'The monitor\'s own error: reference {REF_TOL * 100:.2f} % (0.5 % + 100 ppm/K x 45 K) plus the divider. Worst case ±{wc1 * 100:.2f} % with 1 % resistors '
              f'(99.7 % of boards within ±{mc1 * 100:.2f} %), ±{wc01 * 100:.2f} % with 0.1 % resistors; plus ±{VOS * 1e3:.0f} mV of comparator offset.\n',
              f'Rule: BIAS_OK must come on every board, so the release threshold at its worst (most negative) stays {MARGIN:.1f} V above the weakest VNC '
              f'(least negative: low string, cold, high Vgs(th), hot end); hysteresis {HYST:.1f} V; trip = release + hysteresis. '
              'The old -71 V and the drawn -68.4 V / 1.4 V are shown against the same spread.\n',
              '| String | Divider | Weakest VNC (V) | Strongest VNC (V) | Release, nominal (V) | **Trip, nominal (V)** | Trip range (V) | Margin weakest VNC to the worst release (V) | Margin to the worst trip (V) |',
              '|---|---|---|---|---|---|---|---|---|']
        for s in STRINGS:
            c = sp[s]['corners'][..., 0]
            weakest, strongest = np.nanmax(c), np.nanmin(c)
            for rtol in (0.01, 0.001):
                rel, trip, (tlo, thi) = thresholds(weakest, rtol)
                wc, _ = monitor_tol(rtol)
                relworst = rel * (1 + wc) - VOS
                L.append(f'| {s} | {rtol * 100:g} % | {weakest:.1f} | {strongest:.1f} | {rel:.1f} | **{trip:.1f}** | {tlo:.1f} to {thi:.1f} | {relworst - weakest:.1f} | {tlo - weakest:.1f} |')
                chosen[(s, rtol)] = dict(rel=rel, trip=trip, tlo=tlo, thi=thi, weakest=weakest, strongest=strongest)
        L += ['', 'The earlier thresholds against the 76 V string\'s spread (monitor with 1 % resistors):\n',
              '| Threshold | Release at its worst (V) | Weakest VNC (V) | Result |', '|---|---|---|---|']
        c = sp[list(STRINGS)[0]]
        weakest = np.nanmax(c['corners'][..., 0])
        mcweak = np.nanmax(c['mc'][..., 0], axis=(1, 2, 3))    # each MC board's weakest VNC
        for name, trip, hyst in (('-71 V, no hysteresis (bias_supply.md, 2026-11-20)', -71.0, 0.0), ('-68.4 V, 1.4 V hysteresis (power amp rev B drawing)', -68.4, 1.4)):
            relworst = (trip - hyst) * (1 + wc1) - VOS
            fails = 100 * np.mean(mcweak > (trip - hyst))
            L.append(f'| {name} | {relworst:.1f} | {weakest:.1f} | ' + (f'**fails**: the weakest board is {weakest - relworst:.1f} V short; {fails:.0f} % of the Monte Carlo boards are above the nominal release level at some temperature or load'
                                                                        if weakest > relworst else f'passes with {relworst - weakest:.1f} V') + ' |')
        # ---------------- rail monitor
        rlo, rhi = RAIL_TRIP * (1 + wc01) - VOS, RAIL_TRIP * (1 - wc01) + VOS
        rrel = (RAIL_TRIP - RAIL_HYST) * (1 + wc01) - VOS
        st72 = np.nanmin(sp[S72]['corners'][..., 0])
        izmin = np.nanmin(sp[S72]['corners'][..., 1]) * 1e3
        L += ['', '## Rail monitor (proposed, with the 72 V string)\n',
              'The VNC monitor alone only sees a lost rail after VNC has followed it up to the trip level, 3-13 V hotter than the board\'s own VNC. '
              'A second comparator on the -80 V rail itself trips before VNC moves. It only fits when the string is in regulation on every board '
              f'at the lowest rail (72 V string: lowest string current {izmin:.2f} mA at -78 V; the 76 V string is out of regulation on 38-62 % of the corner cases at 70 °C).\n',
              f'- Trip nominal **{RAIL_TRIP:.1f} V**, hysteresis {RAIL_HYST:.1f} V, 0.1 % divider: trips between {rlo:.1f} and {rhi:.1f} V, releases at {rrel:.1f} V at the worst.',
              f'- Lowest rail in normal use: -78 V at the tab (±2 V), {RAIL_MIN:.1f} V after the 10 Ω fusible resistor at 20 mA: **{rrel - RAIL_MIN:.1f} V** above the worst release level '
              f'({rrel - RAIL_MIN + 1:.1f} V with a ±1 V rail).',
              f'- Strongest VNC with the 72 V string: {st72:.1f} V. A board there has drifted {max(0.0, rhi - st72):.1f} V when the rail monitor trips at its least negative; the typical board has not moved at all.',
              '- It also catches a rail that sags and stays (PSU overloaded): with the VNC monitor alone every bias would sit 3-13 V hot for as long as the rail stays between VNC and the trip level.\n']
        # ---------------- -80 V lost
        L += ['', '## -80 V lost with the HV on\n',
              'The -80 V source is disconnected at full voltage (lead off, or the PSU output stops); the board\'s 100 µF holds the rail, '
              'loaded by the bias circuit itself (5-20 mA). ±15 V stay up. The followers hold VNC until the rail has risen to it; '
              'from there VNC and every bias follow the rail up (hotter) until a monitor trips, clamps the channels (bias = VNC) and drops BIAS_OK. '
              '"Drift" is how much hotter than commanded the bias gets before that. The PSU\'s own output capacitance adds to the 100 µF and stretches every time in proportion. '
              'After the clamp the bias equals VNC, which follows the dying rail toward 0 V: the last two columns.\n',
              '| Design | Board | DAC (V) | bias before (V) | -80 V current (mA) | **BIAS_OK low after (ms)** | hottest bias before the clamp (V) | **drift (V)** | clamped bias (V) | above -40 V after (s) | above -20 V after (s) |',
              '|---|---|---|---|---|---|---|---|---|---|---|']
        c76, c76p, c72 = chosen[(S76, 0.01)], chosen[(S76, 0.001)], chosen[(S72, 0.001)]
        designs = [  # name, string, (trip nominal, least negative, most negative), rail trip (nominal, least negative, most negative)
            ('A. 76 V string, VNC monitor -71 V (2026-11-20 document)', S76, (-71.0,) * 3, (None,) * 3),
            ('B. 76 V string, VNC monitor -68.4 V (drawn)', S76, (-68.4,) * 3, (None,) * 3),
            (f'C. 76 V string, VNC monitor {c76["trip"]:.1f} V, 1 % divider', S76, (c76['trip'], c76['thi'], c76['tlo']), (None,) * 3),
            (f'D. 76 V string, VNC monitor {c76p["trip"]:.1f} V, 0.1 % divider', S76, (c76p['trip'], c76p['thi'], c76p['tlo']), (None,) * 3),
            (f'E. 72 V string, VNC monitor {c72["trip"]:.1f} V, 0.1 % divider', S72, (c72['trip'], c72['thi'], c72['tlo']), (None,) * 3),
            (f'**F. 72 V string, VNC monitor {c72["trip"]:.1f} V and rail monitor {RAIL_TRIP:.1f} V (proposed)**', S72,
             (c72['trip'], c72['thi'], c72['tlo']), (RAIL_TRIP, rhi, rlo)),
        ]
        jobs, labels = [], []
        for name, s, tr, rtr in designs:
            bl = [('typical, 25 °C', board(s), 25.0, tr[0], rtr[0])]
            if name[0] not in 'AB':
                bl += [('largest drift (string +2 %, 70 °C, Vgs(th) -1.0 V, trips at their least negative)', board(s, 1, 2, 0, 0, 2, 2), 70.0, tr[1], rtr[1]),
                       ('smallest drift (string -2 %, 0 °C, Vgs(th) -2.0 V, trips at their most negative)', board(s, -1, 0, 2, 2, 2, 0), 0.0, tr[2], rtr[2])]
            for bname, b, temp, trip, rtrip in bl:
                for dac in (0.5, 1.36, 2.0):
                    jobs.append((b, temp, dac, trip, rtrip))
                    labels.append((name, bname, dac))
        res = pool.map(lost_job, jobs)
        summ = {}
        t40s = [r['t40'] for r in res if r and r.get('t40')]
        t20s = [r['t20'] for r in res if r and r.get('t20')]
        for (name, bname, dac), r in zip(labels, res):
            if r is None or r.get('ms') is None:
                L.append(f'| {name} | {bname} | {dac} | – | – | {(r or {}).get("note", "error")} | – | – | – | – | – |')
                continue
            drift = r['hot'] - r['before']
            L.append(f'| {name} | {bname} | {dac} | {r["before"]:.1f} | {r["ima"]:.1f} | **{r["ms"]:.0f}** | {r["hot"]:.1f} | **{drift:.1f}** | {r["cold"]:.1f} | {fmt(r["t40"], 2)} | {fmt(r["t20"], 2)} |')
            w = summ.setdefault(name, dict(typ=0.0, worst=0.0, ms=[]))
            w['worst'] = max(w['worst'], drift)
            w['ms'].append(r['ms'])
            if bname.startswith('typical'):
                w['typ'] = max(w['typ'], drift)
        L += ['', 'Summary (DAC 0.5 to 2.0 V, bias about -57 to -14 V):\n', '| Design | BIAS_OK low after (ms) | drift, typical board (V) | drift, worst board (V) |', '|---|---|---|---|']
        for name, w in summ.items():
            L.append(f'| {name} | {min(w["ms"]):.0f} to {max(w["ms"]):.0f} | {w["typ"]:.1f} | {w["worst"]:.1f} |')
        # ---------------- tubes
        L += ['', '## How hot the tubes get before the HV is inhibited\n',
              'Static cathode current (plate + screen) and plate dissipation from the tube models in sim/models: at the idle point (70 % of Pa max, the bias loop\'s cap) and with the bias '
              'hotter by the drift above (typical / worst board of each design). The excursion lasts from the moment the rail has risen to VNC until BIAS_OK drops '
              '(tens of ms, inside the times above); the grid follows the bias through the grid leak and coupling cap (22 ms with 220k / 0.1 µF, 4.7 ms with 100k / 47 nF), '
              'so the real peak is somewhat lower. Cells: Ik (mA) / Pa (W).\n']
        cols = [(n.strip('*').split('.')[0], w) for n, w in summ.items()]
        L += ['| Tube | V_ANODE / V_SCREEN (V) | idle: Vg1 (V), Ik / Pa | ' + ' | '.join(f'{k}: +{w["typ"]:.1f} V typ | {k}: +{w["worst"]:.1f} V worst' for k, w in cols) + ' | Vg1 for Ik = 220 mA (V) |',
              '|---|---|---|' + '---|' * (2 * len(cols) + 1)]
        curves = {}
        for tube, model, pamax, va, vs in TUBE_PTS:
            vg, ik, pa = curves[(tube, va)] = tube_curve(model, va, vs)
            vg0 = np.interp(0.7 * pamax, pa, vg) if pa.max() > 0.7 * pamax else 0.0
            cells = []
            for _, w in cols:
                for d in (w['typ'], w['worst']):
                    v = min(vg0 + d, 0.0)
                    cells.append(f'{np.interp(v, vg, ik) * 1e3:.0f} / {np.interp(v, vg, pa):.0f}')
            v220 = np.interp(0.220, ik, vg) if ik.max() > 0.220 else None
            L.append(f'| {tube} | {va:.0f} / {vs:.0f} | {vg0:.1f}, {np.interp(vg0, vg, ik) * 1e3:.0f} / {np.interp(vg0, vg, pa):.0f} | ' + ' | '.join(cells)
                     + f' | {fmt(v220)} |')
        L += ['', 'After BIAS_OK drops the HV supplies stop within 1 ms (their figure) but their outputs stay charged (94 µF each, bleeders only). The clamped bias follows the dying '
              f'rail (with the board\'s 100 µF alone it passes -40 V after {min(t40s):.1f}-{max(t40s):.1f} s'
              + (f' and -20 V after {min(t20s):.1f}-{max(t20s):.1f} s' if t20s else ' and is still below -20 V 5 s after the loss') + '), the tubes turn on and discharge the outputs. That energy is bounded: '
              f'94 µF at 400 V is {0.5 * 94e-6 * 400 ** 2:.1f} J on V_ANODE, shared by four plates rated 25-42 W (calculated, not simulated).\n']
        weak72 = chosen[(S72, 0.001)]['weakest']
        L += [f'Cold bias on the weakest 72 V board (bias = VNC = {weak72:.1f} V at DAC 0), cathode current at V_ANODE 400 V: '
              + ', '.join(f'{tube} (V_SCREEN {vs:.0f} V) {np.interp(weak72, *tube_curve(model, 400.0, vs)[:2]) * 1e3:.2f} mA'
                          for tube, model, vs in (('EL34', 'EL34_R', 370.0), ('6L6GC', '6L6GC_R', 390.0), ('6550', '6550_X', 290.0), ('KT88', 'KT88_X', 320.0))) + '.\n']
        # ---------------- -80 V current
        L += ['', '## -80 V current over the bias range (four channels at the same code)\n',
              '| DAC (V) | bias (V) | typical board, -80 V (mA) | highest over the corners, -82 V (mA) |', '|---|---|---|---|']
        s = S72
        dacs = (0.0, 0.5, 1.0, 1.36, 1.6, 2.0, 2.41, 2.5)
        rt = pool.map(vnc_job, [(board(s), 25.0, d) for d in dacs])
        hi_boards = [board(s, z, 1, 1, v, 1, 1, rt=dict(rz=-RTOL, rgv=-RTOL, rpdn=-RTOL, rs=-RTOL, rpd=-RTOL)) for z in (-1, 1) for v in (0, 2)]
        rh = pool.map(vnc_job, [(b, t, d) for d in dacs for b in hi_boards for t in (0.0, 70.0)])
        rh = np.array(rh).reshape(len(dacs), -1, 5, 4)
        for i, d in enumerate(dacs):
            L.append(f'| {d:.2f} | {rt[i][2, 3]:.1f} | {rt[i][2, 2] * 1e3:.1f} | {rh[i, :, 0, 2].max() * 1e3:.1f} |')
        L += ['', f'String: {s}. The 76 V string with 3.9k draws 0.2-1 mA less in the string. Split at the hot end: 4 x 2.5 mA of mirror current through the followers, '
              '4 x 1.8 mA in the 22k + 22k pull-downs, about 2.5 mA in the string, 47k and 100k.\n']
        # zener dissipation
        L += ['Zener string dissipation at -82 V (corners): ' + '; '.join(
            f'{s}: {np.nanmax(sp[s]["corners"][:, :, :, 0, 1]) * 1e3:.1f} mA, {np.nanmax(sp[s]["corners"][:, :, :, 0, 1]) * STRINGS[s]["vz"] / 2 * 1e3:.0f} mW per diode'
            for s in (S76, S72)) + ' (BZX84: 250 mW at 25 °C).']
    open(os.path.join(RES, 'vnc_monitor.md'), 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    sys.exit(main())
