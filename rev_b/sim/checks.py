#!/usr/bin/env python3
"""Quick checks for the power amp rev B schematic (copied from tube_amplifier_kicad
sim/bias_supply, 2026-11-21; bias.py is an unchanged copy of the master's netlist generator).

1. -80 V rail current with all four channels, against the 13.4 mA allocation (interfaces.md 3.1),
   over the bias range -2.6 .. -74 V.
2. The cathode-current filter: the master's SHUNT netlist has 'Cb1 a2 b1 330n' with node b1
   unconnected (a floating capacitor), so it simulated two cascaded RCs, not the Sallen-Key the
   documents describe. Here: as simulated (b1 floating) against Cb1 returned to the op amp's
   inverting input fb (a unity-gain node: the Sallen-Key that works with the gain of 10).
Usage: python3 rev_b/sim/checks.py
"""
import os
import re
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bias  # noqa: E402


def run(net, ctl):
    with tempfile.TemporaryDirectory() as wd:
        open(os.path.join(wd, 'x.cir'), 'w').write(net + '\n.control\n' + ctl + '\n.endc\n.end\n')
        r = subprocess.run(['ngspice', '-b', 'x.cir'], capture_output=True, text=True, cwd=wd, timeout=600)
        files = {f: np.loadtxt(os.path.join(wd, f)) for f in os.listdir(wd) if f.endswith('.txt')}
    return r.stdout + r.stderr, files


def rail_current():
    rows = []
    for vdac in (0.0, 0.5, 1.0, 1.36, 1.6, 2.0, 2.41, 2.5):
        net = bias.netlist({}, dac=f'DC {vdac}', en='force', nch=4)
        out, f = run(net, 'tran 1m 1.5 1.4 1m\nwrdata op.txt v(bias1) i(Vraw) i(Vcc) i(Vee)')
        d = f['op.txt'][-1]
        rows.append((vdac, d[1], abs(1e3 * d[3]), abs(1e3 * d[5]), abs(1e3 * d[7])))
    return rows


SHUNT = """* cathode current measurement chain
{models}
Ik 0 k PWL({pwl})
Rsh k 0 1
Dprot k 0 DPWR
Rin k a1 10k
Ccl a1 0 10n
Ra a1 a2 47k
Cb1 a2 {cb1} 330n
Rb a2 a3 47k
Cb2 a3 0 330n
XU a3 fb y vcc vee OPA
Rg1 y fb 9k
Rg2 fb 0 1k
Rout y adc 1k
Cadc adc 0 100n
Vcc vcc 0 15
Vee vee 0 -15
.model DPWR D(is=1e-9 rs=0.01 n=1.5)
"""


def shunt(cb1):
    t = np.arange(0, 1.6, 25e-6)
    i = np.full_like(t, 0.050)
    on = (t > 0.3) & (t < 0.7)
    i[on] += 0.35 * np.maximum(0, np.sin(2 * np.pi * 1000 * t[on]))
    i[t > 0.9] = 0.400
    pwl = ' '.join(f'{a:.6g} {b:.5g}' for a, b in zip(t[::2], i[::2]))
    net = SHUNT.format(models=bias.MODELS, pwl=pwl, cb1=cb1)
    out, f = run(net, 'tran 50u 1.6 0 50u\nwrdata sh.txt v(adc)')
    d = f['sh.txt']
    tt, adc = d[:, 0], d[:, 1]
    trip = tt[(tt > 0.9) & (adc > 2.2)]
    win = (tt > 0.6) & (tt < 0.7)
    final = adc[(tt > 0.85) & (tt < 0.9)].mean()
    # settling of the idle->pulses step (target 0.05 + 0.35/pi A x 10 V/A)
    target = 10 * (0.050 + 0.35 / np.pi)
    st = tt[(tt > 0.3) & (tt < 0.7) & (np.abs(adc - target) > 0.005)]
    return dict(trip_ms=(trip[0] - 0.9) * 1e3 if len(trip) else None,
                ripple_mA=(adc[win].max() - adc[win].min()) * 100,
                avg_mA=adc[win].mean() * 100, settle_ms=(st[-1] - 0.3) * 1e3 if len(st) else 0.0,
                peak_overshoot_V=adc[tt > 0.9].max())


def shutdown(thr, en='PULSE(0 5 0.5 1u 1u 50u 100u)'):
    """-80 V source disconnected at 1.5 s (100 uF hold-up), +-15 V stay up; DAC at 2.0 V (about -16 V);
    BIAS_EN starts at 0.5 s (5 V, 10 kHz as interfaces.md 6.3). Returns (ms to BIAS_OK low, hottest bias)."""
    raw = ('Vrs rs 0 PWL(0 0 0.05 -80)\nRrs rs rsw 10\nSoff rsw raw ctl 0 SOFF\n.model SOFF SW(vt=0.5 ron=0.1 roff=1e9)\n'
           'Vctl ctl 0 PWL(0 1 1.5 1 1.5001 0)\nChold raw 0 100u')
    net = bias.netlist({}, dac='DC 2.0', raw_src=raw, vcc_src='Vcc vcc 0 PWL(0 0 0.01 0 0.03 15)',
                       vee_src='Vee vee 0 PWL(0 0 0.01 0 0.03 -15)', en='toggle')
    net = net.replace('Ven en 0 PULSE(0 3.3 0 1u 1u 0.5m 1m)', f'Ven en 0 {en}').replace('V(vnc) > -71', f'V(vnc) > {thr}')
    out, f = run(net, 'tran 0.2m 2.4 0 0.2m\nwrdata pw.txt v(bias1) v(bias_ok) v(vnc)')
    d = f['pw.txt']
    t, vb, ok, vnc = d[:, 0], d[:, 1], d[:, 3], d[:, 5]
    inh = (t > 1.5) & (ok < 0.5)
    on = (t > 0.5) & (vb > -20)
    return ((t[np.argmax(inh)] - 1.5) * 1e3 if inh.any() else None, vb[(t > 1.5)].max(),
            vb[(t > 1.3) & (t < 1.5)].mean(), vnc[(t > 1.3) & (t < 1.5)].mean(),
            (t[np.argmax(on)] - 0.5) * 1e3 if on.any() else None)


def grid(rgl, ccc):
    """150 V peak overdrive for 0.2 s (as the master's grid test): how far the bias node moves, with the
    drawn grid leak / coupling cap (100k / 47n) against the master sim's 220k / 0.1u."""
    net = bias.netlist(dict(rgl=rgl), dac='DC 1.25', en='force',
                       grid_drive='Edr{c} dr{c} 0 drv{c} 0 1\nBdrv{c} drv{c} 0 V = {(time > 0.2 && time < 0.4) ? 150*sin(2*pi*1000*time) : 0}')
    net = net.replace('gl1 dr1 0.1u', f'gl1 dr1 {ccc}')
    out, f = run(net, 'tran 20u 0.8 0 20u\nwrdata gr.txt v(bias1) v(gl1)')
    d = f['gr.txt']
    t, vb, gl = d[:, 0], d[:, 1], d[:, 3]
    base = vb[(t > 0.15) & (t < 0.2)].mean()
    return base, vb[(t > 0.2) & (t < 0.45)].max() - base, gl[(t > 0.2) & (t < 0.42)].min() - base


def vnc_spread():
    """VNC for the zener string at +-2 % and the follower's |Vgs(th)| from 1 to 4 V (DAC at zero)."""
    rows = []
    for zk in (0.98, 1.0, 1.02):
        for vto in (-1.0, -2.5, -4.0):
            net = bias.netlist({}, dac='DC 0', en='force').replace('bv=76', f'bv={76 * zk:.2f}').replace('vto=-2.5', f'vto={vto}')
            out, f = run(net, 'tran 1m 1.5 1.4 1m\nwrdata v.txt v(vnc)')
            rows.append((76 * zk, vto, f['v.txt'][-1][1]))
    return rows


if __name__ == '__main__':
    print('## -80 V rail current, 4 channels (all at the same DAC code)\n')
    print('| Vdac (V) | bias (V) | -80 V (mA) | +15 V (mA) | -15 V (mA) |\n|---|---|---|---|---|')
    for r in rail_current():
        print('| ' + ' | '.join('–' if x is None else f'{x:.2f}' for x in r) + ' |')
    print('\n## Cathode-current filter\n')
    print('| Cb1 to | trip after a step to 400 mA (ms) | ripple, class AB pulses (mA pp) | reading (mA, true 161.4) | settling to 0.5 mA (ms) | max after the step (V) |')
    print('|---|---|---|---|---|---|')
    for name, node in (('floating (as simulated in the master)', 'b1'), ('fb (unity-gain Sallen-Key; not drawn)', 'fb')):
        s = shunt(node)
        print(f"| {name} | {s['trip_ms']:.1f} | {s['ripple_mA']:.2f} | {s['avg_mA']:.1f} | {s['settle_ms']:.0f} | {s['peak_overshoot_V']:.2f} |")
    print('\n## Grid current, 150 V peak overdrive for 0.2 s\n')
    print('| grid leak / coupling cap | bias (V) | bias node moves (V) | most negative grid-leak foot vs bias (V, blocking) |\n|---|---|---|---|')
    for rgl, ccc, name in ((220e3, '0.1u', '220k / 0.1u (master sim)'), (100e3, '47n', '100k / 47n (drawn)')):
        b, mv, blk = grid(rgl, ccc)
        print(f'| {name} | {b:.1f} | {mv:.2f} | {blk:.0f} |')
    print('\n## VNC spread (DAC at zero)\n')
    print('| zener string (V) | follower Vgs(th) (V) | VNC (V) |\n|---|---|---|')
    for z, vto, v in vnc_spread():
        print(f'| {z:.1f} | {vto:.1f} | {v:.2f} |')
    print('\n## VNC monitor threshold: -80 V source lost at 1.5 s, +-15 V up, DAC 2.0 V, BIAS_EN 5 V 10 kHz from 0.5 s\n')
    print('| threshold (V) | bias before (V) | VNC before (V) | commanded bias reached after BIAS_EN starts (ms) | BIAS_OK low after loss (ms) | hottest bias after loss (V) |')
    print('|---|---|---|---|---|---|')
    for thr in (-71, -68.4):
        ms, hot, before, vnc, on = shutdown(thr)
        print(f'| {thr} | {before:.1f} | {vnc:.2f} | {on:.0f} | {ms:.0f} | {hot:.1f} |')
