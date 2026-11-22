"""Large-signal, no load (review U7, E27; SAFE-5): full drive into an open secondary, and a
speaker unplugged while playing. Does the loop oscillate or motorboat, how high do the plates
go, and what limits it (feedback, diodes plate to ground, a safety load on the 8 ohm tap, a
clamp across each primary half)? Writes results/open_load_tran.md and results/open_load_tran.png.

    python3 run_open_load_tran.py      # about 10 minutes on 30 cores
"""
import os
from multiprocessing import Pool

os.environ.setdefault('OMP_NUM_THREADS', '1')

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import nfb
import stability as S

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, 'results')
CAT = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300']
INK, INK2, GRID = '#0b0b0b', '#52514e', '#e4e3df'
STEP = 1e-6
NODES = ['pa', 'pb', 'out', 'gl1', 'gl3', 'ct']
VA_RATING = {'EL34': 800, 'KT88': 800, '6L6GC': 500, '6550': 660}   # DC plate voltage, design max
OPTS = ['method=gear reltol=1e-4', 'method=gear reltol=1e-3 itl4=100', 'method=trap reltol=1e-3 itl4=100']
ONSET = 2.81           # PI input for 5 % THD at 1 kHz, Rf 100k, 400 V, speaker (results/large_signal.md)
VMAX_IN = 18.0         # the PI input limit (PI-4, pi_nfb point 11)


def sim(kw, vin, tstop, step=STEP):
    kw = dict(kw)
    va = kw.pop('va', 400.0)
    nodes = NODES + (['ptvs'] if any(isinstance(c, tuple) for c in kw.get('clamp', []) or []) else [])
    return S.tran(va, vin, tstop, step, nodes, **kw)


def analyse(t, v, f0, t_a, t_b):
    """Peaks in [t_a, t_b]; non-harmonic energy above 20 kHz (oscillation); envelope swing
    below 10 Hz (motorboating) relative to the mean output."""
    m = (t >= t_a) & (t <= t_b)
    pa, pb, out = v['pa'][m], v['pb'][m], v['out'][m]
    r = dict(vp_max=float(max(pa.max(), pb.max())), vp_min=float(min(pa.min(), pb.min())),
             out_pk=float(np.max(np.abs(out))))
    dt = t[1] - t[0]
    y = out - out.mean()
    Y = np.abs(np.fft.rfft(y * np.hanning(len(y))))
    f = np.fft.rfftfreq(len(y), dt)
    harm = np.zeros_like(f, dtype=bool)
    for k in range(1, int(f[-1] / f0) + 1):
        harm |= np.abs(f - k * f0) < 3 * (f[1] - f[0]) + 2.0
    fund = np.sqrt(np.sum(Y[np.abs(f - f0) < 3 * (f[1] - f[0]) + 2.0] ** 2)) + 1e-12
    hf = (f > 20e3) & ~harm
    r['nonharm_db'] = float(20 * np.log10(np.sqrt(np.sum(Y[hf] ** 2)) / fund + 1e-12))
    lf = (f > 0.5) & (f < 0.8 * f0) & ~harm
    r['subharm_db'] = float(20 * np.log10(np.sqrt(np.sum(Y[lf] ** 2)) / fund + 1e-12))
    # grid bias shift (blocking) at the end of the window
    r['grid_shift'] = float(min(np.mean(v['gl1'][m][-int(0.02 / dt):]), np.mean(v['gl3'][m][-int(0.02 / dt):])))
    return r


CASES = []   # key, label, kwargs, vin amplitude, f0, mode ('steady' or 'unplug')


def add(key, label, kw, amp, f0, mode):
    CASES.append((key, label, kw, amp, f0, mode))


BASE = dict(cc=220e-9, rgl=100e3)
for tube in ('EL34', 'KT88', '6L6GC', '6550'):
    for fb in ('100k', 'none', '47k_step'):
        for f0 in (100.0, 1000.0):
            add(('steady', tube, fb, f0, 'none', 1e-9), f"{tube}, fb {fb}, open, {f0:.0f} Hz",
                dict(BASE, tube=tube, fb=fb, load='open', cot=1e-9), VMAX_IN, f0, 'steady')
for tube in ('EL34', 'KT88', '6L6GC', '6550'):
    for f0 in (100.0, 1000.0):
        add(('unplug', tube, '100k', f0, 'none', 1e-9), f"{tube}, fb 100k, unplugged at 150 ms, {f0:.0f} Hz",
            dict(BASE, tube=tube, fb='100k', load='spk95', cot=1e-9, load_switch=0.15), VMAX_IN, f0, 'unplug')
# winding capacitance and the clamps, EL34 and 6L6GC (the lowest plate rating)
for tube in ('EL34', '6L6GC'):
    for cot in (0.0, 470e-12):
        add(('steady', tube, '100k', 100.0, 'none', cot), f"{tube}, fb 100k, open, 100 Hz, winding cap {cot*1e12:.0f} pF",
            dict(BASE, tube=tube, fb='100k', load='open', cot=cot), VMAX_IN, 100.0, 'steady')
    for cl, extra in (('s470', dict(safety=470.0)), ('s220', dict(safety=220.0)),
                      ('s100', dict(safety=100.0)), ('tvs', dict(clamp=[('tvs', 600.0)])),
                      ('dgnd+s220', dict(clamp=['dgnd'], safety=220.0)),
                      ('core100k', dict(rcore=100e3)), ('core30k', dict(rcore=30e3))):
        for mode in ('steady', 'unplug'):
            kw = dict(BASE, tube=tube, fb='100k', load='open' if mode == 'steady' else 'spk95', cot=1e-9, **extra)
            if mode == 'unplug':
                kw['load_switch'] = 0.15
            add((mode, tube, '100k', 100.0, cl, 1e-9), f"{tube}, fb 100k, {mode}, 100 Hz, {cl}", kw, VMAX_IN, 100.0, mode)
# the recommended clamps on every tube type: diodes plate to ground, plus a 600 V clamp per
# primary half or an RC snubber on the 8 ohm tap for the unplug spike
CLAMPS = (('dgnd', dict(clamp=['dgnd'])), ('dgnd+tvs', dict(clamp=['dgnd', ('tvs', 600.0)])),
          ('dgnd+rc', dict(clamp=['dgnd'], zobel=(47.0, 470e-9))))
for tube in ('EL34', 'KT88', '6L6GC', '6550'):
    for cl, extra in CLAMPS:
        for mode in ('steady', 'unplug'):
            for f0 in (100.0, 1000.0):
                kw = dict(BASE, tube=tube, fb='100k', load='open' if mode == 'steady' else 'spk95', cot=1e-9, **extra)
                if mode == 'unplug':
                    kw['load_switch'] = 0.15
                add((mode, tube, '100k', f0, cl, 1e-9), f"{tube}, fb 100k, {mode}, {f0:.0f} Hz, {cl}", kw, VMAX_IN, f0, mode)
for fb in ('none', '47k_step'):
    for cl, extra in CLAMPS[:2]:
        for mode in ('steady', 'unplug'):
            kw = dict(BASE, tube='EL34', fb=fb, load='open' if mode == 'steady' else 'spk95', cot=1e-9, **extra)
            if mode == 'unplug':
                kw['load_switch'] = 0.15
            add((mode, 'EL34', fb, 100.0, cl, 1e-9), f"EL34, fb {fb}, {mode}, 100 Hz, {cl}", kw, VMAX_IN, 100.0, mode)
for cot in (0.0, 470e-12):
    kw = dict(BASE, tube='EL34', fb='100k', load='spk95', cot=cot, clamp=['dgnd', ('tvs', 600.0)], load_switch=0.15)
    add(('unplug', 'EL34', '100k', 100.0, 'dgnd+tvs', cot), f"EL34, fb 100k, unplug, 100 Hz, dgnd+tvs, winding cap {cot*1e12:.0f} pF",
        kw, VMAX_IN, 100.0, 'unplug')
# lower drive into no load: at the onset and below (normal playing levels)
for tube in ('EL34', '6L6GC'):
    for amp in (1.0, ONSET, 5.6):
        add(('drive', tube, '100k', 100.0, f'{amp:.2f}', 1e-9), f"{tube}, fb 100k, open, 100 Hz, {amp:.2f} V at the PI input",
            dict(BASE, tube=tube, fb='100k', load='open', cot=1e-9), amp, 100.0, 'steady')
# reference: the same drive into the speaker (what the plates see when everything is normal)
for tube in ('EL34', '6L6GC'):
    add(('loaded', tube, '100k', 100.0, 'none', 1e-9), f"{tube}, fb 100k, speaker, 100 Hz",
        dict(BASE, tube=tube, fb='100k', load='spk95', cot=1e-9), VMAX_IN, 100.0, 'steady')
    add(('loaded', tube, '100k', 1000.0, 'none', 1e-9), f"{tube}, fb 100k, speaker, 1 kHz",
        dict(BASE, tube=tube, fb='100k', load='spk95', cot=1e-9), VMAX_IN, 1000.0, 'steady')
# idle with no load: does it oscillate on its own (no drive)?
for tube in ('EL34', 'KT88', '6L6GC', '6550'):
    for fb in ('100k', '47k_step'):
        add(('idle', tube, fb, 1000.0, 'none', 1e-9), f"{tube}, fb {fb}, open, idle (10 mV kick)",
            dict(BASE, tube=tube, fb=fb, load='open', cot=1e-9), 0.0, 1000.0, 'idle')


def run_case(c):
    key, label, kw, amp, f0, mode = c
    tr = 2e-3
    if mode == 'idle':
        vin = "Bin pi_src 0 V = {0.01*exp(-((time-5e-3)/1e-4)^2)}"
        tstop = 0.3
    else:
        vin = f"Bin pi_src 0 V = {{{amp:.6g}*sin(2*pi*{f0:.6g}*time)*0.5*(1+tanh((time-0.02)/{tr}))}}"
        tstop = 0.45 if mode == 'unplug' else 0.3
    try:
        t, v = sim(dict(kw), vin, tstop)
    except RuntimeError as e:
        return key, dict(error=str(e)[-300:])
    if mode == 'unplug':
        before = analyse(t, v, f0, 0.10, 0.1499)
        r = analyse(t, v, f0, 0.15, tstop)
        r_after = analyse(t, v, f0, 0.30, tstop)
        r.update(before_vp=before['vp_max'], before_out=before['out_pk'], late_vp=r_after['vp_max'],
                 nonharm_db=r_after['nonharm_db'], subharm_db=r_after['subharm_db'])
        # the flyback right at the moment of unplugging
        m = (t >= 0.15) & (t < 0.16)
        r['flyback'] = float(max(v['pa'][m].max(), v['pb'][m].max()))
    elif mode == 'idle':
        r = analyse(t, v, f0, 0.1, tstop)
        r['out_pk_late'] = float(np.max(np.abs(v['out'][t > 0.2])))
    else:
        r = analyse(t, v, f0, 0.2, tstop)
    mm = t > (0.15 if mode == 'unplug' else 0.2)
    r['vpct'] = float(max(np.max(np.abs(v['pa'][mm] - v['ct'][mm])), np.max(np.abs(v['pb'][mm] - v['ct'][mm]))))
    r['vpmin'] = float(min(v['pa'][mm].min(), v['pb'][mm].min()))
    if 'ptvs' in v:
        m = t > (0.30 if mode == 'unplug' else 0.2)
        r['ptvs'] = float(np.mean(v['ptvs'][m]))
        m = (t >= 0.15) & (t < 0.16) if mode == 'unplug' else m
        r['etvs'] = float(np.sum(np.maximum(v['ptvs'][m], 0)) * (t[1] - t[0]))
    dec = max(1, int(50e-6 / STEP))
    r['t'] = t[::dec]
    r['pa'] = v['pa'][::dec]
    r['out'] = v['out'][::dec]
    return key, r


def main():
    with Pool(min(30, os.cpu_count() or 4)) as p:
        res = dict(p.map(run_case, CASES, chunksize=1))
    lab = {c[0]: c[1] for c in CASES}
    md = ["# Large signal with no load", "",
          "Generated by `run_open_load_tran.py`. Rev B PI, 220n / 100k power coupling, V_ANODE 400 V, OT model",
          "with 1 nF winding capacitance per primary half unless stated. Drive: 18 V peak at the PI input (the",
          "PI-4 limit, +16 dB over the 5 % onset with a speaker), ramped in over 10 ms. 'Steady' = the",
          "load is open from the start; 'unplug' = the speaker model is disconnected at 150 ms while",
          "playing. Plate voltages are to ground (the cathodes sit at about 0 V). 'Non-harmonic > 20 kHz'",
          "is the output energy above 20 kHz that is not a harmonic of the drive (oscillation), 'sub-",
          "harmonic' the energy between 0.5 Hz and 0.8 f0 (motorboating), both relative to the fundamental.", "",
          "| Case | Peak plate (V) | Lowest plate (V) | Output peak (V) | Non-harmonic > 20 kHz | Sub-harmonic | Power grid bias shift (V) | Flyback at unplug (V) | Peak plate before unplug (V) | Clamp: mean W after / J in the unplug spike |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for c in CASES:
        k = c[0]
        r = res[k]
        if 'error' in r:
            md.append(f"| {lab[k]} | failed | | | | | | | | |")
            continue
        fly = f"{r['flyback']:.0f}" if 'flyback' in r else ''
        bef = f"{r['before_vp']:.0f}" if 'before_vp' in r else ''
        outpk = f"{r['out_pk']:.1f}" + (f" (late {r['out_pk_late']:.2g})" if 'out_pk_late' in r else '')
        md.append(f"| {lab[k]} | {r['vp_max']:.0f} | {r['vp_min']:.0f} | {outpk} | {r['nonharm_db']:.0f} dB | "
                  f"{r['subharm_db']:.0f} dB | {r['grid_shift']:.1f} | {fly} | {bef} | "
                  + (f"{r['ptvs']:.1f} W / {r['etvs']*1e3:.0f} mJ" if 'ptvs' in r else '') + " |")
    md += ["", "Plate voltage ratings (DC, design maximum): EL34 800 V (Philips; 2000 V cold), KT88 800 V,",
           "6L6GC 500 V (GE), 6550 600 V (RCA) / 660 V (Tung-Sol). In normal push-pull operation the plate",
           "swings to about twice V_ANODE; the ratings are DC values.", ""]
    # plot: EL34 unplug, none vs clamps
    fig, axs = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    for (k, c) in zip([('unplug', 'EL34', '100k', 100.0, x, 1e-9) for x in ('none', 'dgnd', 'dgnd+tvs', 'dgnd+rc')], CAT):
        r = res.get(k)
        if not r or 'error' in r:
            continue
        axs[0].plot(r['t'] * 1e3, r['pa'], color=c, lw=1, label=k[4])
        axs[1].plot(r['t'] * 1e3, r['out'], color=c, lw=1, label=k[4])
    for ax in axs:
        ax.grid(True, color=GRID, lw=0.6)
        for s in ('top', 'right'):
            ax.spines[s].set_visible(False)
        ax.axvline(150, color=INK2, lw=1, ls=':')
    axs[0].set_ylabel('Plate A to ground (V)', fontsize=9, color=INK2)
    axs[1].set_ylabel('8 Ω tap (V)', fontsize=9, color=INK2)
    axs[1].set_xlabel('ms (speaker unplugged at 150 ms), EL34, 100 Hz, 18 V at the PI input', fontsize=9, color=INK2)
    axs[0].legend(fontsize=8, frameon=False, ncol=4)
    axs[0].set_title('Speaker unplugged while playing: plate voltage and output', fontsize=11, color=INK, loc='left')
    fig.tight_layout()
    fig.savefig(os.path.join(RES, 'open_load_tran.png'), dpi=120)
    plt.close(fig)
    md += ["![Unplug](open_load_tran.png)", ""]
    with open(os.path.join(RES, 'open_load_tran.md'), 'w') as fh:
        fh.write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == '__main__':
    main()
