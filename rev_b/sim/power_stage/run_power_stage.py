#!/usr/bin/env python3
"""Power stage case runner (simulation plan, section 1). Answers Q1-Q3 provisionally.

Writes:
  results/bias_table.md    Q1: Vg1 for the idle targets, bias resolution, bias-noise gain
  results/power_table.md   Q2/Q3: output power at 1% / 5% THD and at full drive, dissipation,
                           screen current and overload, supply current
  results/*.png            summary plots
  out/                     raw per-run data (json), ignored by git

Models: section 0 models (EL34_R, 6L6GC_R measured; KT88_X, 6550_X datasheet fits), with the
errors listed in sim/models/README.md. Results stay provisional until our own tubes are measured.

Usage: python3 run_power_stage.py [--jobs N] [--quick]
"""
import argparse
import json
import math
import os
import sys
from multiprocessing import Pool

import stage

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, 'results')
OUT = os.path.join(HERE, 'out')

SETS = {
    '4x EL34': ['EL34'] * 4,
    '4x 6L6GC': ['6L6GC'] * 4,
    '4x 6550': ['6550'] * 4,
    '4x KT88': ['KT88'] * 4,
    'EL34+6L6GC per side': ['EL34', '6L6GC', 'EL34', '6L6GC'],
    'EL34 side / 6L6GC side': ['EL34', 'EL34', '6L6GC', '6L6GC'],
}
VA = [150, 200, 250, 300, 350, 400, 450, 500]
IDLE = {'cold 40%': 0.4, '60%': 0.6, '70%': 0.7}
DRIVE_IDLE = 0.7
DRIVES = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 100, 130, 160]
TARGET_W = 100.0


def vg2_b(tubes, va):
    """Option B: separate V_SCREEN, follows V_ANODE but held at 90% of the lowest Vg2 rating."""
    return min(va, 0.9 * min(stage.TUBES[t]['vg2'] for t in tubes))


def job_bias(args):
    name, va, screen, frac = args
    tubes = SETS[name]
    vb = vg2_b(tubes, va)
    try:
        r = stage.solve_bias(tubes, va, screen, vb, frac)
        if frac == 0.7:
            r2 = stage.solve_bias(tubes, va, screen, vb, 0.6)
            r['gm'] = [(a - b) / (c - d) if abs(c - d) > 1e-6 else float('nan')
                       for a, b, c, d in zip(r['ia'], r2['ia'], r['vg1'], r2['vg1'])]
            r['gain1'] = stage.bias_gain(tubes, va, screen, vb, r['vg1'], [0])
            r['gain1_hiz'] = stage.bias_gain(tubes, va, screen, vb, r['vg1'], [0],
                                             p=dict(rout_pi=100e3))
            if tubes[0] != tubes[2]:
                r['gain_cm'] = stage.bias_gain(tubes, va, screen, vb, r['vg1'], [0, 1, 2, 3])
    except Exception as e:  # noqa: BLE001 - record and continue
        r = dict(error=str(e)[-500:])
    return (name, va, screen, frac), r


def job_drive(args):
    name, va, screen, drive, bias = args
    tubes = SETS[name]
    try:
        r = stage.run_drive(tubes, va, screen, vg2_b(tubes, va), drive, bias)
    except Exception as e:  # noqa: BLE001
        r = dict(error=str(e)[-500:])
    return (name, va, screen, drive), r


def interp_at_thd(points, thd):
    """Output power where THD last crosses `thd` (%) upwards, linear in drive. The last crossing,
    because class AB crossover distortion can push THD above 1% at low levels before it dips."""
    pts = [p for p in points if 'pout' in p]
    for a, b in reversed(list(zip(pts, pts[1:]))):
        if a['thd'] <= thd < b['thd']:
            t = (thd - a['thd']) / (b['thd'] - a['thd'])
            return a['pout'] + t * (b['pout'] - a['pout']), a, b, t
    return None, None, None, None


def lerp_list(a, b, t, key):
    return [x + t * (y - x) for x, y in zip(a[key], b[key])]


def fmt(x, nd=1):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return '–'
    return f'{x:.{nd}f}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--jobs', type=int, default=os.cpu_count())
    ap.add_argument('--quick', action='store_true', help='EL34 only, 3 anode voltages')
    ap.add_argument('--tables', action='store_true', help='rebuild tables and plots from out/raw.json')
    a = ap.parse_args()
    if a.tables:
        import ast
        raw = json.load(open(os.path.join(OUT, 'raw.json')))
        bias = {ast.literal_eval(k): v for k, v in raw['bias'].items()}
        drive = {ast.literal_eval(k): v for k, v in raw['drive'].items()}
        write_bias_table(bias)
        plots(write_power_table(bias, drive))
        return
    global SETS, VA
    if a.quick:
        SETS = {'4x EL34': SETS['4x EL34']}
        VA = [250, 400, 450]
    os.makedirs(RES, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)

    with Pool(a.jobs) as pool:
        bias_jobs = [(n, va, s, f) for n in SETS for va in VA for s in 'AB' for f in IDLE.values()]
        bias = dict(pool.map(job_bias, bias_jobs))
        drive_jobs = []
        for n in SETS:
            for va in VA:
                for s in 'AB':
                    b = bias[(n, va, s, DRIVE_IDLE)]
                    if 'error' in b:
                        continue
                    drive_jobs += [(n, va, s, d, b['vg1']) for d in DRIVES]
        drive = dict(pool.map(job_drive, drive_jobs))

    with open(os.path.join(OUT, 'raw.json'), 'w') as f:
        json.dump(dict(bias={repr(k): v for k, v in bias.items()},
                       drive={repr(k): v for k, v in drive.items()}), f, indent=1)

    write_bias_table(bias)
    summary = write_power_table(bias, drive)
    plots(summary)
    errs = [k for k, v in list(bias.items()) + list(drive.items()) if 'error' in v]
    print(f'{len(bias)} bias runs, {len(drive)} drive runs, {len(errs)} errors')
    for k in errs[:10]:
        print('  error:', k)


HEADER = ('> **Provisional.** Models EL34_R, 6L6GC_R (Reefman, measured uTracer fits), KT88_X, 6550_X\n'
          '> (our datasheet fits). Push-pull bench errors at full signal: screen current EL34 +5%,\n'
          '> 6550 -5..-8%, KT88 -30%, 6L6GC -42%; power EL34 +29%, 6L6GC -10%, KT88 -23%, 6550 -15..-18%.\n'
          '> See sim/models/README.md. Generated by `run_power_stage.py`; do not edit by hand.\n\n')


def write_bias_table(bias):
    L = ['# Power stage: bias (Q1)\n', HEADER,
         'Vg1 is the bias at the grid-leak foot that gives the idle plate dissipation (fraction of the\n'
         'tube\'s Pa max). Option A: screens from V_ANODE through 1k dropper + 1k per tube. Option B:\n'
         'separate V_SCREEN = min(V_ANODE, 0.9 x lowest Vg2 rating), 1k per tube.\n\n'
         '`gm` is the idle transconductance (secant 60-70%); `mV/mA` is the Vg1 step that moves the idle\n'
         'current by 1 mA. `G1k` is the gain from one tube\'s bias source to the speaker at 1 kHz with the\n'
         'PI driving through 10k; `G1k hi-Z` with a 100k source (a post-PI master at mid setting).\n'
         '**clamped**: the idle target can\'t be reached even at Vg1 = 0 V (low anode voltage); the\n'
         'row is not a valid operating point. Power scaling needs a bias tracking law instead.\n\n',
         '| Tube set | Screen | Va | Idle | Vg1 per tube (V) | Ia per tube (mA) | Vg2 idle (V) | Vg2 rating | gm (mA/V) | mV/mA | G1k | G100 | G1k hi-Z |',
         '|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    for (n, va, s, frac), r in sorted(bias.items(), key=lambda kv: (list(SETS).index(kv[0][0]), kv[0][2], kv[0][1], kv[0][3])):
        tag = [k for k, v in IDLE.items() if v == frac][0]
        if 'error' in r:
            L.append(f'| {n} | {s} | {va} | {tag} | error | | | | | | | | |')
            continue
        tubes = SETS[n]
        rating = min(stage.TUBES[t]['vg2'] for t in tubes)
        vg2 = max(r['vg2'])
        flag = ' **over**' if vg2 > rating else ''
        vg1 = ' / '.join(fmt(x) for x in dict.fromkeys(r['vg1'])) if len(set(tubes)) > 1 else fmt(r['vg1'][0])
        ia = ' / '.join(fmt(x * 1e3) for x in dict.fromkeys(r['ia'])) if len(set(tubes)) > 1 else fmt(r['ia'][0] * 1e3)
        if 'gm' in r:
            gm = min(r['gm']) * 1e3
            step = 1.0 / gm * 1e3 if gm > 0 else float('nan')
            g = r['gain1']
            gh = r['gain1_hiz']
            extra = f'{fmt(gm, 1)} | {fmt(step, 0)} | {g["g1000"]:.4f} | {g["g100"]:.4f} | {gh["g1000"]:.4f}'
        else:
            extra = ' | | | |'
        if max(r['vg1']) > -0.5:
            vg1 += ' **clamped**'
        L.append(f'| {n} | {s} | {va} | {tag} | {vg1} | {ia} | {fmt(vg2, 0)}{flag} | {rating:.0f} | {extra} |')
    open(os.path.join(RES, 'bias_table.md'), 'w').write('\n'.join(L) + '\n')


def write_power_table(bias, drive):
    L = ['# Power stage: output power, dissipation and screen (Q2, Q3)\n', HEADER,
         f'1 kHz sine into 8 ohm (8 ohm tap), idle {int(DRIVE_IDLE * 100)}% of Pa max, PI 10k / 80 V peak soft clip.\n'
         '`P1%`, `P5%`: output power at 1% and 5% THD. `Pmax`: at the hardest drive (160 V peak, PI\n'
         'clipped). `Pa`, `Pg2`: worst tube, average W, at 5% THD and at Pmax. `Vg2>Va`: the largest\n'
         'instantaneous screen-above-plate voltage at Pmax. `Ia avg`: V_ANODE supply current at Pmax\n'
         '(flagged above the 1650TA\'s 403 mA DC rating).\n'
         '`dVg1`: bias shift at the grid at Pmax (grid current charging the coupling caps).\n\n',
         '| Tube set | Screen | Va | Vg2 | P1% (W) | P5% (W) | Pmax (W) | Pa @5% | Pa @max | Pa rating | Pg2 @5% | Pg2 @max | Pg2 rating | Vg2>Va (V) | Ia avg (mA) | dVg1 (V) |',
         '|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    summary = {}
    for n in SETS:
        tubes = SETS[n]
        pa_r = min(stage.TUBES[t]['pa'] for t in tubes)
        pg2_r = min(stage.TUBES[t]['pg2'] for t in tubes)
        for s in 'AB':
            for va in VA:
                b = bias.get((n, va, s, DRIVE_IDLE), {})
                pts = [drive.get((n, va, s, d), {}) for d in DRIVES]
                pts = [p for p in pts if 'pout' in p]
                if not pts or 'error' in b:
                    continue
                if max(b['vg1']) > -0.5:
                    L.append(f'| {n} | {s} | {va} | – | bias clamped at 0 V: not a valid operating point | | | | | | | | | | | |')
                    continue
                p1, *_ = interp_at_thd(pts, 1.0)
                p5, a5, b5, t5 = interp_at_thd(pts, 5.0)
                top = pts[-1]
                pa5 = max(lerp_list(a5, b5, t5, 'pa')) if a5 else None
                pg5 = max(lerp_list(a5, b5, t5, 'pg2')) if a5 else None
                dvg = max(abs(x - y) for x, y in zip(top['vgavg'], b['vg1']))
                vg2 = max(b['vg2'])
                summary[(n, s, va)] = dict(p1=p1, p5=p5, pmax=top['pout'], pg2max=max(top['pg2']),
                                           pamax=max(top['pa']), vg2=vg2)
                L.append(f'| {n} | {s} | {va} | {fmt(vg2, 0)} | {fmt(p1)} | {fmt(p5)} | {fmt(top["pout"])} | '
                         f'{fmt(pa5)} | {fmt(max(top["pa"]))} | {pa_r:.0f} | {fmt(pg5, 2)} | '
                         f'{fmt(max(top["pg2"]), 2)} | {pg2_r:.0f} | {fmt(max(top["ov"]), 0)} | '
                         f'{fmt(top["ianode"] * 1e3, 0)}{" **>403**" if top["ianode"] > 0.403 else ""} | {fmt(dvg, 1)} |')
    # Q2: anode voltage for the target power
    L += ['', f'## Anode voltage for {TARGET_W:.0f} W at 5% THD (linear interpolation in Va)', '',
          '| Tube set | Screen A | Screen B |', '|---|---|---|']
    for n in SETS:
        row = [n]
        for s in 'AB':
            vals = [(va, summary[(n, s, va)]['p5']) for va in VA if (n, s, va) in summary and summary[(n, s, va)]['p5']]
            hit = '> ' + str(VA[-1]) + ' V'
            for (v0, p0), (v1, p1) in zip(vals, vals[1:]):
                if p0 < TARGET_W <= p1:
                    hit = f'{v0 + (TARGET_W - p0) / (p1 - p0) * (v1 - v0):.0f} V'
                    break
            if vals and vals[0][1] >= TARGET_W:
                hit = f'<= {vals[0][0]} V'
            row.append(hit)
        L.append('| ' + ' | '.join(row) + ' |')
    open(os.path.join(RES, 'power_table.md'), 'w').write('\n'.join(L) + '\n')
    return summary


def plots(summary):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True)
    for ax, s in zip(axs, 'AB'):
        for n in SETS:
            xs = [va for va in VA if (n, s, va) in summary and summary[(n, s, va)]['p5']]
            ax.plot(xs, [summary[(n, s, va)]['p5'] for va in xs], marker='o', label=n)
        ax.axhline(TARGET_W, color='grey', ls='--', lw=1)
        ax.set_title(f'Output power at 5% THD, screen option {s} (provisional)')
        ax.set_xlabel('V_ANODE (V)')
        ax.grid(alpha=0.3)
    axs[0].set_ylabel('W into 8 ohm')
    axs[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(RES, 'pout_vs_va.png'), dpi=110)
    fig, axs = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True)
    for ax, s in zip(axs, 'AB'):
        for n in SETS:
            xs = [va for va in VA if (n, s, va) in summary]
            ax.plot(xs, [summary[(n, s, va)]['pg2max'] for va in xs], marker='o', label=n)
        ax.set_title(f'Worst screen dissipation at full drive, option {s} (provisional)')
        ax.set_xlabel('V_ANODE (V)')
        ax.grid(alpha=0.3)
    axs[0].set_ylabel('W per tube')
    axs[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(RES, 'pg2_vs_va.png'), dpi=110)


if __name__ == '__main__':
    sys.exit(main())
