#!/usr/bin/env python3
"""Cathode-current sense filter: variants compared for the over-current trip (SAFE-2) and the
bias loop's reading (PA-4). Review E1 / M27 / U20.

The 2026-11-20 netlist had `Cb1 a2 b1 330n` with node b1 connected to nothing, so the filter
that ran was ONE real pole (10k + 47k + 47k into 330 nF, 4.6 Hz) with a gain of 10, not the
"2nd-order 3.3 Hz Sallen-Key" of the documents. Here that filter is kept as a named variant and
compared with real second-order filters.

Tests, every variant on the same current waveform:
  ac        corner, attenuation at 82 Hz (low E) and 1 kHz
  pulses    the 2026-11-20 test: 50 mA idle, 1 kHz class AB pulses, then a step to 400 mA
  steps     fault steps from 50 mA idle to 230, 440 mA and an arc (10 A, clamped by the shunt diode)
  short     mirror output transistor shorted (bias to +0.9 V) with the EL34 / KT88 models
  overdrive four tubes at full overdrive, one pair mismatched by +-15 %, 82 Hz and 1 kHz, from
            idle (so the onset of the note is included): average cathode current per tube and
            the peak at the comparator against the 220 mA threshold

Writes results/sense_filter.md and results/sense_filter.png. Usage: python3 run_sense_filter.py
"""
import os
import re
import sys
from multiprocessing import Pool

import numpy as np

from run_bias_supply import run, RES, OUT

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'power_stage'))
import stage  # noqa: E402

from sense import THRESH, VARIANTS, ORDER, SHORT, COMMON, subckts, chains  # noqa: E402


def source_net(pwl):
    return ('* sense filter variants\n' + COMMON + subckts() + f'\nIk 0 k PWL({pwl})\nRsh k 0 1\nDprot k 0 DPWR\n' + chains('k', 'a'))


def cols(f, name, n):
    d = f[name]
    return d[:, 0], [d[:, 2 * i + 1] for i in range(n)]


def trip_ms(t, adc, t0):
    m = (t > t0) & (adc > THRESH)
    return (t[np.argmax(m)] - t0) * 1e3 if m.any() else None


# ---------------------------------------------------------------- tests
def t_ac():
    net = ('* ac\n' + COMMON + subckts() + '\nVi k 0 DC 0 AC 1\n' + chains('k', 'a'))
    _, f, out = run(net, 'ac dec 100 0.1 100k\nwrdata ac.txt ' + ' '.join(f'vdb(adc_a_{n})' for n in ORDER))
    fr, g = cols(f, 'ac.txt', len(ORDER))
    res = {}
    for n, gg in zip(ORDER, g):
        gg = gg - gg[0]
        res[n] = dict(f3=fr[np.argmax(gg < -3)], a82=np.interp(82, fr, gg), a1k=np.interp(1000, fr, gg), peak=gg.max(),
                      fr=fr.tolist(), g=gg.tolist())
    return 'ac', res


def t_pulses():
    t = np.arange(0, 2.4, 25e-6)
    i = np.full_like(t, 0.050)
    on = (t > 0.3) & (t < 1.3)
    i[on] += 0.35 * np.maximum(0, np.sin(2 * np.pi * 1000 * t[on]))
    i[t > 1.8] = 0.400
    pwl = ' '.join(f'{a:.6g} {b:.5g}' for a, b in zip(t[::2], i[::2]))
    _, f, out = run(source_net(pwl), 'tran 50u 2.4 0 50u\nwrdata p.txt ' + ' '.join(f'v(adc_a_{n})' for n in ORDER))
    tt, a = cols(f, 'p.txt', len(ORDER))
    target = 10 * (0.050 + 0.35 / np.pi)
    res = {}
    for n, adc in zip(ORDER, a):
        w = (tt > 1.2) & (tt < 1.3)
        res[n] = dict(trip=trip_ms(tt, adc, 1.8), ripple=np.ptp(adc[w]) * 100, avg=adc[w].mean() * 100, target=target * 100,
                      t=tt[::10].tolist(), adc=adc[::10].tolist())
    return 'pulses', res


def t_step(level):
    """Step from 50 mA idle to `level` amperes at 0.5 s (10 us edge)."""
    pwl = f'0 0.05 0.5 0.05 0.50001 {level} 1.5 {level}'
    _, f, out = run(source_net(pwl), 'tran 20u 1.5 0.45 20u\nwrdata s.txt v(k) ' + ' '.join(f'v(adc_a_{n})' for n in ORDER))
    tt, a = cols(f, 's.txt', len(ORDER) + 1)
    res = dict(vk=a[0][-1])
    for n, adc in zip(ORDER, a[1:]):
        final = adc[-1]
        # settling to 5 % of the step (0.5 mA of a 10 mA bias-loop step, the filter being linear)
        st = tt[(tt > 0.5) & (np.abs(adc - final) > 0.05 * (final - 0.5))]
        res[n] = dict(trip=trip_ms(tt, adc, 0.5), settle=(st[-1] - 0.5) * 1e3 if len(st) else 0.0,
                      over=(adc.max() - final) / (final - 0.5) * 100, t=tt[::5].tolist(), adc=adc[::5].tolist())
    return ('step', level), res


OP = {  # tube: (model, V_ANODE, V_SCREEN): PA-6's maximum V_ANODE and the D13 screen setpoints
    'EL34': ('EL34_R', 400.0, 370.0), '6L6GC': ('6L6GC_R', 400.0, 390.0),
    '6550': ('6550_X', 400.0, 290.0), 'KT88': ('KT88_X', 400.0, 320.0),
}


def wrappers(model):
    """The tube with its plate and screen currents scaled by S (a stronger or weaker tube)."""
    return '\n'.join(
        f'.subckt {model}_{tag} A G2 G1 K\nVa A ai 0\nVs G2 si 0\nX1 ai si G1 K {model}\nFa A K Va {s - 1:.3f}\nFs G2 K Vs {s - 1:.3f}\n.ends'
        for tag, s in (('P15', 1.15), ('M15', 0.85)))


def solve(tubes, va, vs, target, extra):
    net = stage.netlist(tubes, va, 'B', vs, 0.0, None, target).replace('.control', extra + '\n.control', 1)
    out = stage.run_ngspice(net)
    vals = dict((m.group(1).lower(), float(m.group(2))) for m in re.finditer(r'^([vi]\([\w.]+\))\s*=\s*([-+0-9.eE]+)', out, re.M))
    if len(vals) < 20:
        raise RuntimeError(out[-2000:])
    return [vals[f'v(b{n})'] for n in range(1, 5)], [abs(vals[f'i(vsa{n})']) for n in range(1, 5)]


def tube_net(tubes, va, vs, drive, vbias, freq, extra):
    net = stage.netlist(tubes, va, 'B', vs, drive, vbias, p=dict(f=freq))
    net = net[:net.index('.control')]
    return net + extra + '\n' + COMMON + subckts() + '\n'


def t_short(tube):
    """Mirror output transistor shorted on tube 1: its bias source goes from the idle value to
    +0.9 V in 2 ms at 0.1 s (the bias node's 1k / 1 uF); the grid follows through the 220k grid leak
    and the 0.1 uF coupling cap (22 ms)."""
    model, va, vs = OP[tube]
    vb, ia = solve([tube] * 4, va, vs, 0.7, '')
    net = tube_net([tube] * 4, va, vs, 0.0, vb, 1000.0, '')
    net = net.replace(f'Vb1 b1 0 DC {vb[0]}', f'Vb1 b1 0 PWL(0 {vb[0]} 0.1 {vb[0]} 0.102 0.9)')
    net += chains('k1', 'a')
    _, f, out = run(net, 'tran 20u 0.5 0 20u\nwrdata m.txt v(k1) v(pa1) v(g1) ' + ' '.join(f'v(adc_a_{n})' for n in ORDER))
    if 'm.txt' not in f:
        raise RuntimeError(out[-2000:])
    tt, a = cols(f, 'm.txt', len(ORDER) + 3)
    ik, pa, vg = a[0], a[1], a[2]
    res = dict(idle=ik[tt < 0.1].mean(), ikmax=ik.max(), pamax=pa.max(), vb=vb[0], t=tt[::5].tolist(), ik=ik[::5].tolist())
    for n, adc in zip(ORDER, a[3:]):
        tr = trip_ms(tt, adc, 0.1)
        res[n] = dict(trip=tr)
        if tr is not None:
            w = (tt >= 0.1) & (tt <= 0.1 + tr * 1e-3)
            res[n].update(ik=ik[w][-1], joule=np.trapz(pa[w], tt[w]))
    return ('short', tube), res


def t_overdrive(a):
    """Four tubes of one type, tube 1 15 % strong and tube 2 15 % weak (same side), tubes 3 and 4
    nominal; each biased to the same idle plate current (the firmware's loop does that). Drive
    starts at 0.1 s from idle. Sense chains on tube 1 and tube 3."""
    tube, drive, freq = a
    model, va, vs = OP[tube]
    extra = wrappers(model)
    stage.TUBES[tube + '+'] = dict(stage.TUBES[tube], model=model + '_P15')
    stage.TUBES[tube + '-'] = dict(stage.TUBES[tube], model=model + '_M15')
    _, ia0 = solve([tube] * 4, va, vs, 0.7, extra)
    tubes = [tube + '+', tube + '-', tube, tube]
    vb, ia = solve(tubes, va, vs, ('ia', [ia0[0]] * 4), extra)
    net = tube_net(tubes, va, vs, drive, vb, freq, extra)
    # the drive starts at 0.1 s
    net = net.replace('.param vclip=', '.param t0=0.1 vclip=').replace('amp*sin(2*pi*f*time)', '(time > t0 ? amp*sin(2*pi*f*(time-t0)) : 0)')
    net += chains('k1', 'a') + '\n' + chains('k3', 'c')
    step = 20e-6 if freq < 200 else 5e-6
    tstop = 0.9
    names = ['v(k1)', 'v(k2)', 'v(k3)', 'v(k4)', 'v(out)'] + [f'v(adc_a_{n})' for n in ORDER] + [f'v(adc_c_{n})' for n in ORDER]
    _, f, out = run(net, f'tran {step} {tstop} 0 {step}\nwrdata o.txt ' + ' '.join(names), timeout=3000)
    if 'o.txt' not in f:
        raise RuntimeError(out[-2000:])
    tt, c = cols(f, 'o.txt', len(names))
    nper = max(1, int(round(0.1 * freq)))
    w = tt >= tstop - nper / freq
    res = dict(idle=[x[tt < 0.1].mean() for x in c[:4]], avg=[x[w].mean() for x in c[:4]], pk=[x[w].max() for x in c[:4]],
               pout=np.mean(c[4][w] ** 2) / 8.0, vb=vb)
    # highest 100 ms running average of the true cathode current (the onset of the note)
    k = int(0.1 / step)
    for i in (0, 2):
        cs = np.cumsum(np.interp(np.arange(0, tstop, step), tt, c[i]))
        res[f'avg100_{i}'] = ((cs[k:] - cs[:-k]) / k).max()
    for j, tag in ((5, 'a'), (5 + len(ORDER), 'c')):
        for n, adc in zip(ORDER, c[j:j + len(ORDER)]):
            res[(tag, n)] = dict(max=adc.max() * 100, ss=adc[w].mean() * 100, sspk=adc[w].max() * 100, ripple=np.ptp(adc[w]) * 100,
                                 trip=trip_ms(tt, adc, 0.1))
    if tube == 'KT88' and drive == 160.0 and freq < 200:
        res['trace'] = dict(t=tt[::25].tolist(), ik=c[0][::25].tolist(),
                            adc={n: (c[5 + i][::25] * 100).tolist() for i, n in enumerate(ORDER)})
    return ('od', tube, drive, freq), res


DRIVES = (30.0, 60.0, 160.0)
FREQS = (82.0, 1000.0)
STEPS = (0.23, 0.44, 10.0)


def job(a):
    try:
        if a[0] == 'ac':
            return t_ac()
        if a[0] == 'pulses':
            return t_pulses()
        if a[0] == 'step':
            return t_step(a[1])
        if a[0] == 'short':
            return t_short(a[1])
        if a[0] == 'od':
            return t_overdrive(a[1:])
    except Exception as e:  # noqa: BLE001
        return a, dict(error=str(e)[-1500:])


def ms(x):
    return 'no trip' if x is None else f'{x:.0f}'


def main():
    os.makedirs(RES, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    jobs = [('ac',), ('pulses',)] + [('step', s) for s in STEPS] + [('short', t) for t in ('EL34', 'KT88')] + \
           [('od', t, d, f) for t in OP for d in DRIVES for f in FREQS]
    with Pool() as pool:
        res = dict(pool.map(job, jobs, chunksize=1))
    for k, v in res.items():
        if 'error' in v:
            print('ERROR', k, v['error'][-800:], file=sys.stderr)
    ac, pu = res['ac'], res['pulses']
    L = ['# Cathode-current sense filter: variants\n',
         '> Generated by `run_sense_filter.py`; do not edit. ngspice-47, behavioural op amp (bias.py), tube models from sim/models.',
         '> Chain in every variant: 1 Ω shunt with a power diode across it, 10k / 10 nF, the filter, gain 10, 1k / 100 nF to the ADC and the comparator (2.20 V = 220 mA).\n',
         '## Variants\n', '| Variant | Circuit | Op amps per tube | -3 dB (Hz) | at 82 Hz (dB) | at 1 kHz (dB) |', '|---|---|---|---|---|---|']
    for n in ORDER:
        L.append(f'| **{SHORT[n]}** | {VARIANTS[n][0]} | {VARIANTS[n][1]} | {ac[n]["f3"]:.1f} | {ac[n]["a82"]:.0f} | {ac[n]["a1k"]:.0f} |')
    L += ['', 'The 2026-11-20 run and the power amp rev B drawing are the first row: one pole, not two (the second 47k only adds to the first; -20 dB per decade up to the 1.6 kHz poles of the input and output RCs).',
          'Returning Cb1 to the inverting input is not a clean Sallen-Key: that node is the 900 Ω feedback divider, so the capacitor feeds the ripple forward and the attenuation stops at about -35 to -40 dB.\n']
    # ---------------- trip time
    L += ['## Over-current trip time (ms after the fault starts; comparator at 220 mA)\n',
          '| Variant | step 50 → 230 mA | step 50 → 400 mA (the 2026-11-20 case) | step 50 → 440 mA (2x the threshold) | arc: 50 mA → 10 A (the diode clamps the shunt at '
          f'{res[("step", 10.0)]["vk"]:.2f} V) | mirror short, EL34 | mirror short, KT88 |', '|---|---|---|---|---|---|---|']
    for n in ORDER:
        L.append(f'| {SHORT[n]} | {ms(res[("step", 0.23)][n]["trip"])} | {ms(pu[n]["trip"])} | {ms(res[("step", 0.44)][n]["trip"])} | {ms(res[("step", 10.0)][n]["trip"])} | '
                 + ' | '.join(ms(res[('short', t)][n]['trip']) for t in ('EL34', 'KT88')) + ' |')
    L += ['', 'Mirror short (the bias circuit\'s one single-point failure): the bias source goes to +0.9 V in 2 ms; the grid follows through the 220k grid leak and the 0.1 µF coupling cap. '
          'V_ANODE 400 V, V_SCREEN at the D13 setpoint, tubes idling at 70 % of Pa max, no signal.\n',
          '| Tube | idle Ik (mA) | Ik the fault settles at (mA) | plate dissipation there (W) | Variant | trip (ms) | Ik at the trip (mA) | plate energy from the fault to the trip (J) |', '|---|---|---|---|---|---|---|---|']
    for t in ('EL34', 'KT88'):
        r = res[('short', t)]
        for n in ORDER:
            x = r[n]
            L.append(f'| {t} | {r["idle"] * 1e3:.0f} | {r["ikmax"] * 1e3:.0f} | {r["pamax"]:.0f} | {SHORT[n]} | {ms(x["trip"])} | '
                     + (f'{x["ik"] * 1e3:.0f} | {x["joule"]:.1f} |' if x['trip'] is not None else '– | – |'))
    # ---------------- ripple and reading
    L += ['', '## Ripple and reading\n',
          f'Class AB pulses as in the 2026-11-20 run (50 mA idle + 350 mA peak half sines at 1 kHz, true average {10 * (0.05 + 0.35 / np.pi) * 100:.1f} mA); '
          '"10 mA step": time for a bias-loop step to settle to 0.5 mA (5 %), and its overshoot. '
          '(The "400 ms settling" of the 2026-11-20 results was the length of that test\'s window: the 1.2 mA ripple never stayed inside ±0.5 mA.)\n',
          '| Variant | reading (mA) | ripple, 1 kHz pulses (mA pp) | 10 mA step: settling to 0.5 mA (ms) | overshoot (%) |', '|---|---|---|---|---|']
    s23 = res[('step', 0.23)]
    for n in ORDER:
        L.append(f'| {SHORT[n]} | {pu[n]["avg"]:.1f} | {pu[n]["ripple"]:.2f} | {s23[n]["settle"]:.0f} | {max(0.0, s23[n]["over"]):.1f} |')
    # ---------------- overdrive
    L += ['', '## False-trip margin at full overdrive\n',
          'Four tubes of one type at V_ANODE 400 V and the D13 screen setpoint, 1650TA into 8 Ω, PI soft-clipping at 80 V peak. Tube 1 is 15 % strong, its partner 15 % weak, '
          'the other side nominal; all four idle at the same current (70 % of Pa max for the nominal tube). The drive starts from idle and lasts 0.8 s. '
          'Sine drive: a guitar signal has a lower average for the same peak, so these are upper figures. Models: KT88 and 6L6GC read low on current at full signal '
          '(plate -12 % for KT88, sim/models), so add that.\n',
          '### Average cathode current per tube (mA)\n',
          '| Tubes | drive (V peak) | f (Hz) | output (W) | idle | strong tube (+15 %) | weak tube (-15 %) | nominal tube | strong tube, highest 100 ms average | strong tube, peak |', '|---|---|---|---|---|---|---|---|---|---|']
    worst = {}
    for t in OP:
        for d in DRIVES:
            for fq in FREQS:
                r = res[('od', t, d, fq)]
                if 'error' in r:
                    L.append(f'| 4x {t} | {d:.0f} | {fq:.0f} | error | | | | | | |')
                    continue
                L.append(f'| 4x {t} | {d:.0f} | {fq:.0f} | {r["pout"]:.0f} | {r["idle"][0] * 1e3:.0f} | {r["avg"][0] * 1e3:.0f} | {r["avg"][1] * 1e3:.0f} | {r["avg"][2] * 1e3:.0f} | '
                         f'{r["avg100_0"] * 1e3:.0f} | {r["pk"][0] * 1e3:.0f} |')
                w = worst.setdefault(t, dict(avg=0.0, avgn=0.0, v={n: dict(max=0.0, maxn=0.0, rip82=0.0, rip1k=0.0, trip=False) for n in ORDER}))
                w['avg'] = max(w['avg'], r['avg100_0'] * 1e3)
                w['avgn'] = max(w['avgn'], r['avg100_2'] * 1e3)
                for n in ORDER:
                    x, y = r[('a', n)], r[('c', n)]
                    v = w['v'][n]
                    v['max'] = max(v['max'], x['max'])
                    v['maxn'] = max(v['maxn'], y['max'])
                    v['trip'] = v['trip'] or x['trip'] is not None
                    key = 'rip82' if fq < 200 else 'rip1k'
                    v[key] = max(v[key], x['ripple'])
    L += ['', '### Highest level at the comparator (mA; the trip is at 220 mA), worst drive level and frequency, onset included\n',
          '| Tubes | highest 100 ms average, strong / nominal tube (mA) | ' + ' | '.join(SHORT[n] for n in ORDER) + ' |', '|---|---|' + '---|' * len(ORDER)]
    for t, w in worst.items():
        L.append(f'| 4x {t}, strong tube | {w["avg"]:.0f} / {w["avgn"]:.0f} | ' + ' | '.join(
            (f'**{w["v"][n]["max"]:.0f} (trips)**' if w['v'][n]['trip'] else f'{w["v"][n]["max"]:.0f} (margin {220 - w["v"][n]["max"]:.0f})') for n in ORDER) + ' |')
        L.append(f'| 4x {t}, nominal tube | | ' + ' | '.join(f'{w["v"][n]["maxn"]:.0f}' for n in ORDER) + ' |')
    L += ['', '### Ripple at the comparator and the ADC at full overdrive (mA peak-to-peak, strong tube, worst drive level)\n',
          '| Tubes | ' + ' | '.join(f'{SHORT[n]}: 82 Hz / 1 kHz' for n in ORDER) + ' |', '|---|' + '---|' * len(ORDER)]
    for t, w in worst.items():
        L.append(f'| 4x {t} | ' + ' | '.join(f'{w["v"][n]["rip82"]:.1f} / {w["v"][n]["rip1k"]:.2f}' for n in ORDER) + ' |')
    L += ['', 'ADC reading error: a single conversion taken at any moment is off by up to half the ripple above while the amp is played. '
          'The bias loop works on the idle current, so it must only act when there is no signal (the reading rises with the signal in class AB whatever the filter); '
          'at idle the ripple is zero and the error is the 12-bit step (0.06 mA) plus offsets. After a bias step the loop waits for the settling time in the table above before it reads again.\n']
    open(os.path.join(RES, 'sense_filter.md'), 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))
    plot(res)


def plot(res):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(2, 2, figsize=(13, 8))
    ac = res['ac']
    for n in ORDER:
        axs[0, 0].semilogx(ac[n]['fr'], ac[n]['g'], label=SHORT[n])
    axs[0, 0].set_xlim(0.5, 1e4)
    axs[0, 0].set_ylim(-100, 5)
    axs[0, 0].set_title('Response (dB, relative to DC)')
    s = res[('step', 0.44)]
    for n in ORDER:
        axs[0, 1].plot((np.array(s[n]['t']) - 0.5) * 1e3, np.array(s[n]['adc']) * 100, label=SHORT[n])
    axs[0, 1].axhline(220, color='k', lw=0.8, ls=':')
    axs[0, 1].set_xlim(-5, 150)
    axs[0, 1].set_title('Step 50 → 440 mA: level at the comparator (mA), ms')
    pu = res['pulses']
    for n in ORDER:
        t = np.array(pu[n]['t'])
        m = (t > 0.25) & (t < 0.8)
        axs[1, 0].plot(t[m], np.array(pu[n]['adc'])[m] * 100, label=SHORT[n])
    axs[1, 0].set_title('1 kHz class AB pulses from 0.3 s: reading (mA)')
    r = res.get(('od', 'KT88', 160.0, 82.0), {})
    if 'trace' in r:
        tr = r['trace']
        axs[1, 1].plot(tr['t'], np.array(tr['ik']) * 1e3, color='0.8', lw=0.5, label='cathode current')
        for n in ORDER:
            axs[1, 1].plot(tr['t'], tr['adc'][n], label=SHORT[n])
        axs[1, 1].axhline(220, color='k', lw=0.8, ls=':')
        axs[1, 1].set_ylim(0, 400)
        axs[1, 1].set_title('KT88 strong tube, full overdrive at 82 Hz from idle (mA)')
    for ax in axs.flat:
        ax.grid(alpha=0.3, which='both')
        ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(RES, 'sense_filter.png'), dpi=100)


if __name__ == '__main__':
    sys.exit(main())
