#!/usr/bin/env python3
"""Bias tracking law for power scaling (simulation plan, section 1, Q1 "tracking law").

When V_ANODE (and V_SCREEN) is turned down to lower the power, the bias has to follow. Three laws:

  fixed70  idle plate dissipation held at 70% of Pa max (the first-pass rule; can't be reached at
           low V_ANODE even at Vg1 = 0)
  track    Vg1 scaled with the screen supply: Vg1 = Vg1(450 V) * Vscreen / Vscreen(450 V). The cathode
           current depends on Vg2/mu + Vg1, so this keeps the operating point's shape and scales the
           idle current about as V^1.5.
  constI   idle plate current held at its 450 V value (servo)

For each law, tube set, screen option and V_ANODE: the bias, idle dissipation, crossover
distortion (THD at 1 W), output power at 5% THD and at full drive, screen dissipation.

Writes results/bias_law.md and results/bias_law.png; raw data in out/bias_law.json.
Usage: python3 run_bias_law.py [--jobs N]
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
}
VA = [150, 200, 250, 300, 350, 400, 450, 500]
VA_REF = 450
LAWS = ['fixed70', 'track', 'constI']
DRIVES = [0, 1, 2, 4, 8, 15, 25, 35, 45, 60, 80, 160]


def vscreen(tubes, va, screen):
    if screen == 'A':
        return va
    return min(va, 0.9 * min(stage.TUBES[t]['vg2'] for t in tubes))


def job_ref(args):
    name, screen = args
    tubes = SETS[name]
    return (name, screen), stage.solve_bias(tubes, VA_REF, screen, vscreen(tubes, VA_REF, screen), 0.7)


def job_bias(args):
    name, screen, va, law, ref = args
    tubes = SETS[name]
    vs = vscreen(tubes, va, screen)
    try:
        if law == 'fixed70':
            vg1 = stage.solve_bias(tubes, va, screen, vs, 0.7)['vg1']
        elif law == 'constI':
            vg1 = stage.solve_bias(tubes, va, screen, vs, ('ia', ref['ia']))['vg1']
        else:
            s = vs / vscreen(tubes, VA_REF, screen)
            vg1 = [v * s for v in ref['vg1']]
        return (name, screen, va, law), dict(vg1=vg1)
    except Exception as e:  # noqa: BLE001
        return (name, screen, va, law), dict(error=str(e)[-300:])


def job_drive(args):
    name, screen, va, law, d, vg1 = args
    tubes = SETS[name]
    try:
        r = stage.run_drive(tubes, va, screen, vscreen(tubes, va, screen), max(d, 1e-3), vg1)
    except Exception as e:  # noqa: BLE001
        r = dict(error=str(e)[-300:])
    return (name, screen, va, law, d), r


def at_power(pts, pw):
    """THD where the output power first reaches pw (log interpolation)."""
    for a, b in zip(pts, pts[1:]):
        if a['pout'] <= pw < b['pout'] and a['pout'] > 0:
            t = (math.log(pw) - math.log(a['pout'])) / (math.log(b['pout']) - math.log(a['pout']))
            return a['thd'] + t * (b['thd'] - a['thd'])
    return None


def p_at_thd(pts, thd):
    for a, b in reversed(list(zip(pts, pts[1:]))):
        if a['thd'] <= thd < b['thd']:
            t = (thd - a['thd']) / (b['thd'] - a['thd'])
            return a['pout'] + t * (b['pout'] - a['pout'])
    return None


def fmt(x, nd=1):
    return '–' if x is None else f'{x:.{nd}f}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--jobs', type=int, default=os.cpu_count())
    a = ap.parse_args()
    os.makedirs(RES, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    with Pool(a.jobs) as pool:
        ref = dict(pool.map(job_ref, [(n, s) for n in SETS for s in 'AB']))
        bias = dict(pool.map(job_bias, [(n, s, va, law, ref[(n, s)]) for n in SETS for s in 'AB'
                                        for va in VA for law in LAWS]))
        jobs = [(n, s, va, law, d, b['vg1']) for (n, s, va, law), b in bias.items() if 'vg1' in b
                for d in DRIVES]
        drive = dict(pool.map(job_drive, jobs))
    json.dump(dict(ref={repr(k): v for k, v in ref.items()}, bias={repr(k): v for k, v in bias.items()},
                   drive={repr(k): v for k, v in drive.items()}), open(os.path.join(OUT, 'bias_law.json'), 'w'))

    rows = {}
    for (n, s, va, law), b in bias.items():
        if 'vg1' not in b:
            continue
        pts = [drive.get((n, s, va, law, d), {}) for d in DRIVES]
        if any('pout' not in p for p in pts):
            continue
        tubes = SETS[n]
        idle = pts[0]
        rows[(n, s, va, law)] = dict(
            vg1=min(b['vg1']), clamped=max(b['vg1']) > -0.5,
            ia=idle['ianode'] / 4 * 1e3,
            pidle=max(p / stage.TUBES[t]['pa'] for p, t in zip(idle['pa'], tubes)) * 100,
            thd1w=at_power(pts[1:], 1.0), p5=p_at_thd(pts[1:], 5.0), pmax=pts[-1]['pout'],
            pg2max=max(pts[-1]['pg2']), pg2r=min(stage.TUBES[t]['pg2'] for t in tubes))
    write(rows)
    plot(rows)
    errs = [k for k, v in list(bias.items()) + list(drive.items()) if 'error' in v]
    print(f'{len(rows)} cases, {len(errs)} errors')


def write(rows):
    L = ['# Power stage: bias tracking law for power scaling\n',
         '> Models: EL34_R, 6L6GC_R (Reefman, measured), KT88_X, 6550_X (datasheet fits); see',
         '> sim/models/README.md for their errors. Generated by `run_bias_law.py`; do not edit.\n',
         f'Reference: 70% idle dissipation at V_ANODE = {VA_REF} V. Laws: **fixed70** (70% of Pa max at every',
         'setting), **track** (Vg1 proportional to the screen supply), **constI** (idle current held at the',
         f'{VA_REF} V value). Screen option A: V_SCREEN = V_ANODE through 1k; B: separate, capped at 90% of',
         'the lowest Vg2 rating. `Idle %`: worst tube\'s idle plate dissipation as % of Pa max. `THD@1W`:',
         'crossover distortion indicator. `clamped`: bias pinned at 0 V, idle target not reachable.\n',
         '| Tube set | Screen | Va | Law | Vg1 (V) | Ia idle (mA/tube) | Idle % | THD@1W (%) | P5% (W) | Pmax (W) | Pg2 max (W) / rating |',
         '|---|---|---|---|---|---|---|---|---|---|---|']
    for (n, s, va, law), r in sorted(rows.items(), key=lambda kv: (list(SETS).index(kv[0][0]), kv[0][1], kv[0][2], LAWS.index(kv[0][3]))):
        L.append(f'| {n} | {s} | {va} | {law} | {fmt(r["vg1"])}{" clamped" if r["clamped"] else ""} | {fmt(r["ia"])} | '
                 f'{fmt(r["pidle"], 0)} | {fmt(r["thd1w"], 2)} | {fmt(r["p5"])} | {fmt(r["pmax"])} | '
                 f'{fmt(r["pg2max"], 2)} / {r["pg2r"]:.0f} |')
    open(os.path.join(RES, 'bias_law.md'), 'w').write('\n'.join(L) + '\n')


def plot(rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(2, 2, figsize=(12, 8))
    styles = {'fixed70': '-', 'track': '--', 'constI': ':'}
    colors = dict(zip(SETS, ['C0', 'C1', 'C2', 'C3', 'C4']))
    for n in SETS:
        for law in LAWS:
            xs = [va for va in VA if (n, 'B', va, law) in rows]
            get = lambda k: [rows[(n, 'B', va, law)][k] for va in xs]  # noqa: E731
            lab = f'{n} {law}' if law == 'track' else None
            axs[0, 0].plot(xs, get('vg1'), styles[law], color=colors[n], label=lab)
            axs[0, 1].plot(xs, get('pidle'), styles[law], color=colors[n])
            axs[1, 0].plot(xs, [x if x is not None else float('nan') for x in get('thd1w')], styles[law], color=colors[n])
            axs[1, 1].plot(xs, [x if x is not None else float('nan') for x in get('p5')], styles[law], color=colors[n])
    axs[0, 0].set_title('Bias Vg1 (V)')
    axs[0, 1].set_title('Idle plate dissipation, % of Pa max')
    axs[1, 0].set_title('THD at 1 W (%): crossover')
    axs[1, 1].set_title('Output power at 5% THD (W)')
    for ax in axs.flat:
        ax.set_xlabel('V_ANODE (V)')
        ax.grid(alpha=0.3)
    axs[0, 0].legend(fontsize=7, title='solid fixed70, dashed track, dotted constI', title_fontsize=7)
    fig.suptitle('Bias tracking laws, screen option B (provisional)')
    fig.tight_layout()
    fig.savefig(os.path.join(RES, 'bias_law.png'), dpi=110)


if __name__ == '__main__':
    sys.exit(main())
