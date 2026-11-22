#!/usr/bin/env python3
"""Bias supply simulation runner (simulation plan, section 2). Circuit: bias.py.

Writes results/bias_supply.md and results/bias_supply.png; raw output in out/.
Usage: python3 run_bias_supply.py
"""
import os
import re
import subprocess
import sys
import tempfile
from multiprocessing import Pool

import numpy as np

import bias
import sense

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, 'results')
OUT = os.path.join(HERE, 'out')


def run(net, ctl, timeout=900):
    with tempfile.TemporaryDirectory(dir=OUT) as wd:
        open(os.path.join(wd, 'x.cir'), 'w').write(net + '\n.control\n' + ctl + '\n.endc\n.end\n')
        r = subprocess.run(['ngspice', '-b', 'x.cir'], capture_output=True, text=True, cwd=wd, timeout=timeout)
        files = {}
        for f in os.listdir(wd):
            if f.endswith('.txt'):
                try:
                    files[f] = np.loadtxt(os.path.join(wd, f))
                except ValueError:
                    pass
    out = r.stdout + r.stderr
    vals = dict((k.lower(), float(v)) for k, v in re.findall(r'^(\w+)\s*=\s*([-+0-9.eE]+)', out, re.M))
    vals.update({k.lower(): float(v) for k, v in re.findall(r'^(v\(\w+\))\s*=\s*([-+0-9.eE]+)', out, re.M)})
    return vals, files, out


# ------------------------------------------------------------------ tests
def t_transfer(raw):
    net = bias.netlist(dict(raw=raw), dac='DC 0', en='force')
    _, f, out = run(net, 'dc Vdac1 0 2.5 0.025\nwrdata tr.txt v(bias1)')
    return ('transfer', raw), dict(d=f['tr.txt'][:, 0].tolist(), v=f['tr.txt'][:, 1].tolist())


FAILS = {
    'normal (DAC 1.25 V, enabled)': (dict(), dict(dac='DC 1.25', en='force')),
    'DAC at zero': (dict(), dict(dac='DC 0', en='force')),
    'DAC output open (unpowered, high-Z)': (dict(rflt=1e9), dict(dac='DC 1.25', en='force')),
    '+15 V missing': (dict(vcc=0.0), dict(dac='DC 1.25', en='force')),
    '-15 V missing': (dict(vee=0.0), dict(dac='DC 1.25', en='force')),
    '+15 and -15 V missing': (dict(vcc=0.0, vee=0.0), dict(dac='DC 1.25', en='force')),
    'watchdog line static high (firmware stuck)': (dict(), dict(dac='DC 1.25', en='3.3')),
    'watchdog line low / control card missing': (dict(), dict(dac='DC 1.25', en='0')),
    'DAC at full scale, enabled (hottest command)': (dict(), dict(dac='DC 2.5', en='force')),
}


def t_fail(name):
    p, kw = FAILS[name]
    net = bias.netlist(p, **kw)
    v, _, out = run(net, 'op\nprint v(bias1) v(vnc) v(bias_ok)')
    return ('fail', name), dict(v=v.get('v(bias1)'), vnc=v.get('v(vnc)'), ok=v.get('v(bias_ok)'))


def t_fail_special(name):
    if name == 'one VNC follower open':
        net = bias.netlist({}, dac='DC 1.25', en='force').replace('Mvnc raw zf vs1 PHV', '* Mvnc open')
    elif name == 'both VNC followers open':
        net = bias.netlist({}, dac='DC 1.25', en='force').replace('Mvnc raw zf vs1 PHV', '* open').replace('Mvnc2 raw zf vs2 PHV', '* open')
    elif name == 'mirror output transistor shorted (single-point failure)':
        net = bias.netlist({}, dac='DC 0', en='force') + '\nRshort m31 o1 1'
    v, _, out = run(net, 'op\nprint v(bias1) v(vnc) v(bias_ok)')
    return ('fail', name), dict(v=v.get('v(bias1)'), vnc=v.get('v(vnc)'), ok=v.get('v(bias_ok)'))


def t_noise():
    res = {}
    for tag, p in (('all', {}), ('no DAC noise', dict(en_dac=1e-15)), ('no zener noise', dict(en_z=1e-15))):
        net = bias.netlist(p, dac='DC 1.25 AC 1', en='force')
        v, _, out = run(net, 'noise v(bias1) Vdac1 dec 20 20 20k\nsetplot noise2\nprint onoise_total')
        res[tag] = v.get('onoise_total')
    # supply rejection: raw, +15
    net = bias.netlist({}, dac='DC 1.25', en='force').replace('Vraw raw 0 DC -80.0', 'Vraw raw 0 DC -80.0 AC 1')
    _, f, _ = run(net, 'ac dec 10 1 200k\nwrdata psrr.txt vdb(bias1)')
    net2 = bias.netlist({}, dac='DC 1.25', en='force').replace('Vcc vcc 0 DC 15.0', 'Vcc vcc 0 DC 15.0 AC 1')
    _, f2, _ = run(net2, 'ac dec 10 1 200k\nwrdata psrr.txt vdb(bias1)')
    res['psrr_raw'] = f['psrr.txt'].tolist()
    res['psrr_vcc'] = f2['psrr.txt'].tolist()
    return ('noise',), res


def t_step(kind):
    if kind == 'small up':
        dac = 'PWL(0 1.0 0.3 1.0 0.3001 1.25)'
    elif kind == 'small down':
        dac = 'PWL(0 1.25 0.3 1.25 0.3001 1.0)'
    else:
        dac = 'PWL(0 0.3 0.3 0.3 0.3001 2.2)'
    net = bias.netlist({}, dac=dac, en='force')
    _, f, _ = run(net, 'tran 0.1m 0.6 0 0.1m\nwrdata st.txt v(bias1)')
    d = f['st.txt']
    return ('step', kind), dict(t=d[:, 0].tolist(), v=d[:, 1].tolist())


def t_grid():
    drive = 'Vdr{c} dr{c} 0 PWL(0 0 0.2 0 0.2001 0) \nBdr{c} dr{c}x 0 V = {(time > 0.2 && time < 0.4) ? 150*sin(2*pi*1000*time) : 0}'
    net = bias.netlist({}, dac='DC 1.25', en='force', grid_drive='Edr{c} dr{c} 0 drv{c} 0 1\nBdrv{c} drv{c} 0 V = {(time > 0.2 && time < 0.4) ? 150*sin(2*pi*1000*time) : 0}')
    _, f, out = run(net, 'tran 20u 0.8 0 20u\nwrdata gr.txt v(bias1) v(gl1)')
    d = f['gr.txt']
    return ('grid',), dict(t=d[:, 0].tolist(), v=d[:, 1].tolist(), gl=d[:, 3].tolist())


def t_power(kind):
    # the PSU's -80 V output: ramps up, then disconnects at 1.5 s (the rail decays through its loads)
    raw = ('Vrs rs 0 PWL(0 0 0.05 -80)\nRrs rs rsw 10\nSoff rsw raw ctl 0 SOFF\n.model SOFF SW(vt=0.5 ron=0.1 roff=1e9)\n'
           'Vctl ctl 0 PWL(0 1 1.5 1 1.5001 0)\nChold raw 0 100u')
    if kind == 'raw collapses first':
        vcc = 'Vcc vcc 0 PWL(0 0 0.01 0 0.03 15 1.7 15 1.71 0)'
        vee = 'Vee vee 0 PWL(0 0 0.01 0 0.03 -15 1.7 -15 1.71 0)'
    elif kind == 'raw collapses, low-voltage rails stay up':
        vcc = 'Vcc vcc 0 PWL(0 0 0.01 0 0.03 15)'
        vee = 'Vee vee 0 PWL(0 0 0.01 0 0.03 -15)'
    else:
        vcc = 'Vcc vcc 0 PWL(0 0 0.01 0 0.03 15 1.4 15 1.41 0)'
        vee = 'Vee vee 0 PWL(0 0 0.01 0 0.03 -15 1.4 -15 1.41 0)'
    # DAC already at a hot setting from t=0; the watchdog starts toggling at 0.5 s (firmware up)
    net = bias.netlist({}, dac='DC 2.0', raw_src=raw, vcc_src=vcc, vee_src=vee, en='toggle', nch=4)
    net = net.replace('Ven en 0 PULSE(0 3.3 0 1u 1u 0.5m 1m)', 'Ven en 0 PULSE(0 3.3 0.5 1u 1u 0.5m 1m)')
    _, f, out = run(net, 'tran 0.2m 3.0 0 0.2m\nwrdata pw.txt v(bias1) v(raw) v(vcc) v(bias_ok)')
    d = f['pw.txt']
    return ('power', kind), dict(t=d[:, 0].tolist(), v=d[:, 1].tolist(), raw=d[:, 3].tolist(), vcc=d[:, 5].tolist(),
                                 ok=d[:, 7].tolist())


def t_watchdog_stop():
    net = bias.netlist({}, dac='DC 1.25', en='stop 1.0')
    _, f, _ = run(net, 'tran 0.2m 1.6 0 0.2m\nwrdata wd.txt v(bias1)')
    d = f['wd.txt']
    return ('wdstop',), dict(t=d[:, 0].tolist(), v=d[:, 1].tolist())


def t_shunt():
    """The 2026-11-20 test on the recommended filter and on the one that run really simulated
    (sense.py): 50 mA idle, 1 kHz class AB half-wave pulses (peak 350 mA) on top from 0.3 to 1.3 s,
    then a fault step to 400 mA at 1.8 s. More cases: run_sense_filter.py."""
    t = np.arange(0, 2.4, 25e-6)
    i = np.full_like(t, 0.050)
    on = (t > 0.3) & (t < 1.3)
    i[on] += 0.35 * np.maximum(0, np.sin(2 * np.pi * 1000 * t[on]))
    i[t > 1.8] = 0.400
    pwl = ' '.join(f'{a:.6g} {b:.5g}' for a, b in zip(t[::2], i[::2]))
    names = (sense.RECOMMENDED, sense.AS_SIMULATED)
    net = ('* cathode current measurement chain\n' + sense.COMMON + sense.subckts() + f'\nIk 0 k PWL({pwl})\nRsh k 0 1\nDprot k 0 DPWR\n'
           + sense.chains('k', 'a'))
    _, f, out = run(net, 'tran 50u 2.4 0 50u\nwrdata sh.txt ' + ' '.join(f'v(adc_a_{n})' for n in names))
    d = f.get('sh.txt')
    if d is None:
        raise RuntimeError(out[-2000:])
    return ('shunt',), dict(t=d[:, 0].tolist(), adc=d[:, 1].tolist(), adc_old=d[:, 3].tolist(), avg=0.050 + 0.35 / np.pi)


def job(args):
    kind = args[0]
    try:
        if kind == 'transfer':
            return t_transfer(args[1])
        if kind == 'fail':
            return t_fail(args[1])
        if kind == 'fails':
            return t_fail_special(args[1])
        if kind == 'noise':
            return t_noise()
        if kind == 'step':
            return t_step(args[1])
        if kind == 'grid':
            return t_grid()
        if kind == 'power':
            return t_power(args[1])
        if kind == 'wdstop':
            return t_watchdog_stop()
        if kind == 'shunt':
            return t_shunt()
    except Exception as e:  # noqa: BLE001
        return args, dict(error=str(e)[-1500:])


def settle(t, v, t0, tol):
    t = np.asarray(t)
    v = np.asarray(v)
    final = v[-1]
    idx = np.where((t > t0) & (np.abs(v - final) > tol))[0]
    return (t[idx[-1]] - t0) if len(idx) else 0.0


def main():
    os.makedirs(RES, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    jobs = [('transfer', r) for r in (-78.0, -80.0, -82.0)] + [('fail', n) for n in FAILS] + \
           [('fails', 'one VNC follower open'), ('fails', 'both VNC followers open'),
            ('fails', 'mirror output transistor shorted (single-point failure)')] + \
           [('noise',)] + [('step', k) for k in ('small up', 'small down', 'large up')] + [('grid',)] + \
           [('power', k) for k in ('raw collapses first', 'low-voltage rails collapse first',
                                   'raw collapses, low-voltage rails stay up')] + [('wdstop',), ('shunt',)]
    with Pool() as pool:
        res = dict(pool.map(job, jobs))
    errs = {k: v['error'] for k, v in res.items() if 'error' in v}
    for k, e in errs.items():
        print('ERROR', k, e[-600:])
    write(res)
    plot(res)


def write(res):
    L = ['# Bias supply: simulation results\n', '> Generated by `run_bias_supply.py`; do not edit. Circuit: bias.py.',
         '> Generic device models; behavioural op amp (1 MHz, 10 nV/rtHz). Load: 220k grid leak, 0.1 uF coupling cap.',
         '> Reference as proposed 2026-11-22: 72 V zener string, followers with Vgs(th) -1.5 V, VNC monitor at -63.0 V and rail monitor at -75 V',
         '> (tolerances: [vnc_monitor.md](vnc_monitor.md)); sense filter: two real poles ([sense_filter.md](sense_filter.md)).\n']
    # transfer
    tr = res[('transfer', -80.0)]
    d, v = np.array(tr['d']), np.array(tr['v'])
    fit = np.polyfit(d, v, 1)
    lin = d <= 2.4          # above about 2.45 V the typical board's output saturates near 0 V
    fit = np.polyfit(d[lin], v[lin], 1)
    nl = np.max(np.abs(v[lin] - np.polyval(fit, d[lin])))
    L += ['## Transfer\n', f'Vg1 = {fit[1]:.2f} V + {fit[0]:.2f} V/V x Vdac (DAC 0-2.5 V): **{v[0]:.1f} V (DAC 0, cold) to {v[-1]:.1f} V (full scale)**; '
          f'non-linearity {nl * 1e3:.0f} mV up to 2.4 V (the output saturates near 0 V just below full scale). 12-bit DAC: {fit[0] * 2.5 / 4096 * 1e3:.1f} mV per code; 16-bit: {fit[0] * 2.5 / 65536 * 1e3:.2f} mV.\n']
    for r in (-78.0, -82.0):
        x = res[('transfer', r)]
        L.append(f'- Raw rail {r:.0f} V: cold end {x["v"][0]:.2f} V, mid scale {np.interp(1.25, x["d"], x["v"]):.2f} V '
                 f'(against {np.interp(1.25, d, v):.2f} V at -80 V).')
    # fail-safe
    L += ['', '## Fail-safe (SAFE-1)\n', f'Commanded value in every case except "DAC at zero" and "full scale": {res[("fail", "normal (DAC 1.25 V, enabled)")]["v"]:.1f} V (DAC 1.25 V).\n',
          '| Condition | Vg1 (V) | BIAS_OK | Result |', '|---|---|---|---|']
    vnorm = res[('fail', 'normal (DAC 1.25 V, enabled)')]['v']
    for k, r in res.items():
        if k[0] != 'fail':
            continue
        vv = r.get('v')
        if vv is None:
            ok = 'error'
        elif vv < -65:
            ok = 'cold'
        elif 'full scale' in k[1]:
            ok = 'commanded (hottest setting)'
        elif abs(vv - vnorm) < 0.5:
            ok = 'still controlled (commanded value)'
        elif r.get('ok') is not None and r['ok'] < 0.5:
            ok = f'hotter by {vv - vnorm:.1f} V, **caught: BIAS_OK drops and inhibits the HV**'
        else:
            ok = f'**hotter by {vv - vnorm:.1f} V: must be caught by the over-current trip (SAFE-2)**'
        okv = '–' if r.get('ok') is None else ('high' if r['ok'] > 0.5 else 'low')
        L.append(f'| {k[1]} | {vv:.1f} | {okv} | {ok} |' if vv is not None else f'| {k[1]} | – | – | error |')
    wd = res[('wdstop',)]
    t, vv = np.array(wd['t']), np.array(wd['v'])
    en_v = vv[np.argmin(abs(t - 0.95))]
    cold = (t > 1.0) & (vv < -60)
    tcold = (t[np.argmax(cold)] - 1.0) * 1e3 if cold.any() else None
    L += ['', f'Watchdog: while it toggles the bias is enabled ({en_v:.1f} V at 0.95 s); when the toggling stops (stuck high at 1.0 s) the bias reaches -60 V after '
          + (f'**{tcold:.0f} ms**.' if tcold is not None else '**never (within 0.6 s)**.')]
    # noise
    n = res[('noise',)]
    pr = np.array(n['psrr_raw'])
    pv = np.array(n['psrr_vcc'])
    L += ['', '## Noise and supply rejection\n',
          f'Output noise at the bias node, 20 Hz-20 kHz: **{n["all"] * 1e6:.2f} µVrms** (without DAC noise {n["no DAC noise"] * 1e6:.2f}, '
          f'without zener noise {n["no zener noise"] * 1e6:.2f}). Target from section 1: 100 µVrms per tube.\n',
          f'Raw -80 V rail to the bias node: {np.interp(100, pr[:, 0], pr[:, 1]):.0f} dB at 100 Hz, {np.interp(1e3, pr[:, 0], pr[:, 1]):.0f} dB at 1 kHz, '
          f'{np.interp(1e5, pr[:, 0], pr[:, 1]):.0f} dB at 100 kHz. +15 V rail: {np.interp(100, pv[:, 0], pv[:, 1]):.0f} / {np.interp(1e3, pv[:, 0], pv[:, 1]):.0f} / '
          f'{np.interp(1e5, pv[:, 0], pv[:, 1]):.0f} dB.']
    # step
    L += ['', '## Step response (DAC step at 0.3 s)\n', '| Step | Settling to 0.1 V | to 10 mV |', '|---|---|---|']
    for k in ('small up', 'small down', 'large up'):
        s = res[('step', k)]
        L.append(f'| {k} ({s["v"][0]:.1f} → {s["v"][-1]:.1f} V) | {settle(s["t"], s["v"], 0.3, 0.1) * 1e3:.0f} ms | {settle(s["t"], s["v"], 0.3, 0.01) * 1e3:.0f} ms |')
    # grid current
    g = res[('grid',)]
    t, vb, gl = np.array(g['t']), np.array(g['v']), np.array(g['gl'])
    base = vb[np.argmin(abs(t - 0.19))]
    L += ['', '## Grid current (150 V peak drive into the grid circuit, 0.2-0.4 s)\n',
          f'Bias node moves by at most **{np.max(np.abs(vb[t > 0.2] - base)) * 1e3:.1f} mV**. The grid-leak side of the coupling cap shifts by '
          f'{np.min(gl[(t > 0.2) & (t < 0.42)]) - base:.1f} V (blocking: that is the coupling cap, not the supply) and recovers with the 0.1 uF x 220k time constant.']
    # power sequencing
    L += ['', '## Start-up and shutdown (four channels, DAC already at a hot setting, 2.0 V, from t = 0; watchdog starts at 0.5 s; the -80 V source disconnects at 1.5 s)\n']
    for k in ('raw collapses first', 'low-voltage rails collapse first', 'raw collapses, low-voltage rails stay up'):
        p = res[('power', k)]
        t, vb, raw, ok = np.array(p['t']), np.array(p['v']), np.array(p['raw']), np.array(p['ok'])
        okt = t[np.argmax((t > 0.2) & (ok > 0.5))]
        inh = (t > 1.5) & (ok < 0.5)
        inh_t = (t[np.argmax(inh)] - 1.5) * 1e3 if inh.any() else None
        ii = np.argmax(inh) if inh.any() else len(t) - 1
        vcmd = vb[(t > 1.2) & (t < 1.38)].mean()
        hotmax = vb[(t > 1.5) & (t <= t[ii] + 0.001)].max()
        before = vb[(t > 0.1) & (t < 0.5)]
        tcold = t[np.argmax((t > 0.0) & (vb < -65))]
        on = t[np.argmax((t > 0.5) & (vb > vcmd - 1))]
        L.append(f'- {k}: the bias is below -65 V **{tcold * 1e3:.0f} ms** after the -80 V rail starts rising (it starts from 0 V like every node); '
                 f'from 0.1 s until the watchdog starts it stays between {before.min():.1f} and {before.max():.1f} V (cold); '
                 f'it reaches the commanded value ({vcmd:.1f} V) {(on - 0.5) * 1e3:.0f} ms after the watchdog starts. '
                 + f'BIAS_OK goes high {(okt) * 1e3:.0f} ms after power-on. After the -80 V source disconnects (1.5 s, 100 µF hold-up): '
                 + (f'BIAS_OK drops (HV inhibit) after **{inh_t:.0f} ms**; '
                    + (f'the bias has drifted {hotmax - vcmd:.1f} V hotter by then.' if hotmax - vcmd > 0.05 else 'the bias is never hotter than commanded before that.') if inh_t is not None
                    else 'BIAS_OK never drops.'))
    # shunt
    s = res[('shunt',)]
    t = np.array(s['t'])
    L += ['', '## Cathode-current measurement chain\n',
          '1 Ω shunt (diode-clamped), 10k / 10 nF input filter, the sense filter, gain 10, 1k / 100 nF to the ADC: 10 V/A, '
          '0-2.5 V = 0-250 mA. Hardware over-current comparator at 2.2 V (220 mA). Fault cases, overdrive margins and the other '
          'filter variants: [sense_filter.md](sense_filter.md).\n',
          '| Filter | idle 50 mA reads (mA) | class AB pulses, average ' + f'{s["avg"] * 1e3:.1f}' + ' mA, read (mA) | ripple (mA pp) | trip after a step to 400 mA (ms) |', '|---|---|---|---|---|']
    for name, key in ((sense.RECOMMENDED, 'adc'), (sense.AS_SIMULATED, 'adc_old')):
        adc = np.array(s[key])
        m = (t > 1.2) & (t < 1.3)
        tr = (t > 1.8) & (adc > sense.THRESH)
        L.append(f'| {sense.SHORT[name]}: {sense.VARIANTS[name][0]} | {adc[np.argmin(abs(t - 0.29))] * 100:.1f} | {adc[m].mean() * 100:.1f} | {np.ptp(adc[m]) * 100:.2f} | '
                 + (f'{(t[np.argmax(tr)] - 1.8) * 1e3:.0f}' if tr.any() else 'no trip') + ' |')
    open(os.path.join(RES, 'bias_supply.md'), 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))


def plot(res):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(2, 3, figsize=(15, 8))
    tr = res[('transfer', -80.0)]
    axs[0, 0].plot(tr['d'], tr['v'])
    axs[0, 0].set_title('Transfer: DAC (V) → Vg1 (V)')
    for k in ('small up', 'small down', 'large up'):
        s = res[('step', k)]
        t = np.array(s['t'])
        v = np.array(s['v'])
        axs[0, 1].plot((t - 0.3) * 1e3, (v - v[0]) / (v[-1] - v[0]), label=k)
    axs[0, 1].set_xlim(-10, 200)
    axs[0, 1].set_title('Step response (normalised), ms after the DAC step')
    axs[0, 1].legend(fontsize=7)
    n = res[('noise',)]
    pr = np.array(n['psrr_raw'])
    axs[0, 2].semilogx(pr[:, 0], pr[:, 1], label='-80 V raw rail')
    pv = np.array(n['psrr_vcc'])
    axs[0, 2].semilogx(pv[:, 0], pv[:, 1], label='+15 V rail')
    axs[0, 2].set_title('Supply rejection to the bias node (dB)')
    axs[0, 2].legend(fontsize=7)
    for k, ax in zip(('raw collapses first', 'raw collapses, low-voltage rails stay up'), (axs[1, 0], axs[1, 1])):
        p = res[('power', k)]
        ax.plot(p['t'], p['v'], label='bias')
        ax.plot(p['t'], p['raw'], ':', label='raw -80 V')
        ax.plot(p['t'], p['vcc'], '--', label='+15 V')
        ax.plot(p['t'], np.array(p['ok']) * 10, '-.', label='BIAS_OK x10')
        ax.axvline(0.5, color='grey', lw=0.8)
        ax.set_title(f'Start-up / shutdown: {k}', fontsize=9)
        ax.legend(fontsize=7)
    s = res[('shunt',)]
    axs[1, 2].plot(s['t'], np.array(s['adc_old']) * 100, lw=0.8, label='one pole 4.6 Hz, as simulated 2026-11-20 (mA)')
    axs[1, 2].plot(s['t'], np.array(s['adc']) * 100, label='two real poles, recommended (mA)')
    axs[1, 2].axhline(220, color='k', ls=':', lw=0.8, label='over-current trip')
    axs[1, 2].set_title('Cathode current chain (mA)')
    axs[1, 2].legend(fontsize=7)
    for ax in axs.flat:
        ax.grid(alpha=0.3, which='both')
    fig.tight_layout()
    fig.savefig(os.path.join(RES, 'bias_supply.png'), dpi=100)


if __name__ == '__main__':
    sys.exit(main())
