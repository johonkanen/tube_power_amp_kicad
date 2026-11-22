"""Output stage stability with and without a speaker (review U7, K3, E3, E27): netlist layer.

Wraps nfb.netlist (which is left unchanged) with what this study needs:

- the rev B phase inverter (PI-1): 12AX7 long-tailed pair, constant-current tail (2.07 mA,
  finite output resistance 1 Mohm and 30 pF, as the PI + FX rev B session modelled a DN2540),
  equal 100k plates, PI input 10n, second grid 22n, W24 cable + power tube input capacitance
  60 pF per side, 25k source (the attenuator);
- the four supported tube types, each with its own V_SCREEN setpoint (D13) and idle current
  (constant-current bias law, sim/power_stage/results/bias_law.md);
- loads: 8 ohm resistor, a speaker model with its resonance at 80, 95 or 110 Hz, no load,
  a short, and a safety resistor on the 8 ohm tap;
- the power tube coupling cap and grid leak, and the OT winding capacitance (each primary half
  to the centre tap) as parameters;
- an optional LF shelf in each channel's feedback arm (Rsh || Csh in series with Rf);
- clamps for the large-signal runs (diodes plate to ground, a TVS plate to centre tap).
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nfb  # noqa: E402
import stage  # noqa: E402  (nfb put sim/power_stage on the path)

# V_SCREEN setpoint (D13, sim/power_stage) and idle plate current per tube (constI law at 400 V)
TYPES = {
    'EL34':  dict(vg2=370.0, ia=0.044),
    'KT88':  dict(vg2=320.0, ia=0.067),
    '6L6GC': dict(vg2=390.0, ia=0.050),
    '6550':  dict(vg2=290.0, ia=0.068),
}

# Rev B PI (PI-1) as the PI + FX session simulated it (rev_b/sim/pi_nfb/run_open_load.py, case c)
PI_REVB = dict(ccs=2.07e-3, ra1=100e3, ra2=100e3, cin=10e-9, cg2=22e-9, rs=25e3,
               rccs=1e6, cccs=30e-12, cdrv=60e-12)

FB = {  # per-channel feedback amount (VOX-8): net override, feedback on
    'none': ({}, False),
    '100k': (dict(rf=100e3, cf=22e-12), True),                                  # about 6 dB
    '47k': (dict(rf=47e3, cf=47e-12), True),                                    # about 11 dB
    '47k_step': (dict(rf=47e3, cf=47e-12, rstep=470.0, cstep=10e-9), True),     # with the step network
}

SPK = nfb.SPEAKER          # 6.4 ohm, 0.7 mH (30 ohm eddy), 46 ohm peak at 95 Hz, Q about 3.4


def speaker_lines(fs=95.0, name='spk'):
    k = 95.0 / fs          # same Q and peak, resonance moved to fs
    s = SPK
    return (f"R{name}re out {name}1 {s['re']}\nL{name}le {name}1 {name}2 {s['le']}\n"
            f"R{name}le {name}1 {name}2 {s['rle']}\nR{name}rm {name}2 0 {s['rm']}\n"
            f"L{name}lm {name}2 0 {s['lm'] * k}\nC{name}cm {name}2 0 {s['cm'] * k}\n")


def load_lines(load):
    """'r8', 'spk80' / 'spk95' / 'spk110', 'open', 'short', 'r:<ohms>'."""
    if load == 'r8':
        return "Rload out 0 8\n"
    if load.startswith('spk'):
        return speaker_lines(float(load[3:]))
    if load == 'open':
        return "Rload out 0 1e7\n"
    if load == 'short':
        return "Rload out 0 0.01\n"
    if load.startswith('r:'):
        return f"Rload out 0 {load[2:]}\n"
    raise ValueError(load)


def _vg2(va, tubes):
    return min(va, min(TYPES[t]['vg2'] for t in tubes))


_bias = {}


def _bias_for(va, tubes=("EL34",) * 4):
    key = (va, tuple(tubes))
    if key not in _bias:
        ia = [TYPES[t]['ia'] for t in tubes]
        _bias[key] = stage.solve_bias(list(tubes), va, 'B', _vg2(va, tubes), ('ia', ia))['vg1']
    return _bias[key]


# nfb.netlist looks these up as module globals at call time
nfb.vg2_for = _vg2
nfb.bias_for = _bias_for


def netlist(va, pres, res, analysis, tube='EL34', load='spk95', cc=47e-9, rgl=100e3, fb='100k',
            cot=0.0, shelf=None, safety=None, clamp=None, pi=None, stage_extra=None,
            loop_break=False, options='method=gear reltol=1e-4', load_switch=None, ccs_sat=False,
            rcore=None, pi_leak_ref=None, zobel=None):
    """pi_leak_ref: return the PI grid leaks to this fixed voltage instead of the tail top.
    rcore: OT core loss as a plate-to-plate resistance. ccs_sat: saturating CCS (transients).
    shelf: (Rsh, Csh) in series with Rf at its speaker end. safety: ohms across the 8 ohm tap.
    clamp: set of 'dgnd' (diode ground -> each plate), ('tvs', V) (bidirectional clamp plate to
    centre tap). load_switch: (t_open, load) for transients: the load is disconnected at t_open
    (a speaker unplugged while playing)."""
    net, on = FB[fb]
    net = dict(net)
    if cot:
        net['cot'] = cot
    if zobel:
        net['rzob'], net['czob'] = zobel
    P = dict(PI_REVB, **(pi or {}))
    sp = dict(cc=cc, rgl=rgl, **(stage_extra or {}))
    tubes = [tube] * 4 if isinstance(tube, str) else list(tube)
    n = nfb.netlist(va, pres, res, analysis, mode='grid2', load='resistor', pol=-1, nfb=on,
                    tubes=tubes, pi=P, net=net, loop_break=loop_break, options=options, stage_p=sp)
    # load
    ll = load_lines(load)
    if load_switch:
        t_open = load_switch
        ll = ll.replace(' out ', ' outl ')
        ll += (f"Sunplug out outl uctl 0 swunplug\nVuctl uctl 0 PWL(0 1 {t_open} 1 {t_open + 50e-6} 0)\n"
               ".model swunplug sw(vt=0.5 vh=0.01 ron=1m roff=1e9)\n")
    assert "Rload out 0 8\n" in n
    n = n.replace("Rload out 0 8\n", ll)
    # real CCS and drive-line capacitance (rev B), as rev_b/sim/pi_nfb/nfb.py
    if P.get('rccs'):
        n = n.replace("Rtail pi_top 0 10meg", f"Rtail pi_top 0 {P['rccs']}")
    if ccs_sat and P.get('ccs'):
        # transients: the real CCS (DN2540 + source resistor) runs out of current as its drain
        # approaches its source; an ideal source would drive the tail top to kilovolts when both
        # triodes cut off. Same small-signal behaviour at the operating point (tail top about 10 V).
        assert f"Itail pi_top 0 {P['ccs']}" in n
        n = n.replace(f"Itail pi_top 0 {P['ccs']}", f"Btail pi_top 0 I = {{{P['ccs']}*tanh(max(V(pi_top), 0)/2)}}")
    extra = ''
    if P.get('cccs'):
        extra += f"Cccs pi_top 0 {P['cccs']}\n"
    if P.get('cdrv'):
        extra += f"Cdrv1 o1 0 {P['cdrv']}\nCdrv2 o2 0 {P['cdrv']}\n"
    if shelf and on:
        rsh, csh = shelf
        src = 'vtest' if loop_break else 'out'
        n = n.replace(f"Rf {src} fx ", f"Rf shx fx ").replace(f"Cf {src} fx ", f"Cf shx fx ")
        extra += f"Rsh {src} shx {rsh}\nCsh {src} shx {csh}\n"
    if safety:
        extra += f"Rsafety out 0 {safety}\n"
    if pi_leak_ref is not None:
        # PI grid leaks returned to a fixed DC reference instead of the CCS tail top
        assert "Rg1 pi_gx pi_top" in n and "Rg2 pi_g2 pi_top" in n
        n = n.replace("Rg1 pi_gx pi_top", "Rg1 pi_gx pi_ref").replace("Rg2 pi_g2 pi_top", "Rg2 pi_g2 pi_ref")
        extra += f"Vpiref pi_ref 0 {pi_leak_ref}\n"
    if rcore:
        # OT core loss as a resistance plate to plate (not in the datasheet: an assumption)
        extra += f"Rcore pa pb {rcore}\n"
    if clamp:
        for c in clamp:
            if c == 'dgnd':
                extra += ("Dpa 0 pa dclamp\nDpb 0 pb dclamp\n"
                          ".model dclamp d(is=1e-9 n=1.8 rs=0.5 bv=2000 cjo=10p tt=50n)\n")
            elif c == 'dgnd_rgp':
                # power amp rev B part: Vishay RGP02-20E (2 kV, 0.5 A, trr 300 ns), one per plate
                extra += ("Dpa 0 pa drgp\nDpb 0 pb drgp\n"
                          ".model drgp d(is=5e-9 n=2.0 rs=1.2 bv=2000 ibv=5u cjo=8p tt=200n)\n")
            elif isinstance(c, tuple) and c[0] == 'tvsr':
                # power amp rev B part: two bidirectional TVS in series per half (P6KE350CA x2):
                # string breakdown bv at 1 mA, dynamic resistance rs (datasheet VC at IPP), capacitance cj
                _, v, rs, cj = c
                extra += (f"Dta1 pa ta1 dtvs\nDta2 ctx ta1 dtvs\nDtb1 pb tb1 dtvs\nDtb2 cty tb1 dtvs\n"
                          f"Vtvsa ct ctx 0\nVtvsb ct cty 0\n"
                          f"Btvsp ptvs 0 V = {{-(V(pa)-V(ct))*I(Vtvsa) - (V(pb)-V(ct))*I(Vtvsb)}}\n"
                          f".model dtvs d(is=1e-12 n=1.5 rs={rs / 2} bv={v} ibv=1m cjo={2 * cj})\n")
            elif isinstance(c, tuple) and c[0] == 'tvs':
                v = c[1]
                # bidirectional clamp across each primary half (back-to-back zener behaviour)
                extra += (f"Dta1 pa ta1 dtvs\nDta2 ctx ta1 dtvs\nDtb1 pb tb1 dtvs\nDtb2 cty tb1 dtvs\n"
                          f"Vtvsa ct ctx 0\nVtvsb ct cty 0\n"
                          f"Btvsp ptvs 0 V = {{-(V(pa)-V(ct))*I(Vtvsa) - (V(pb)-V(ct))*I(Vtvsb)}}\n"
                          f".model dtvs d(is=1e-12 n=1.5 rs=2 bv={v} ibv=1m cjo=100p)\n")
    if extra:
        n = n.replace(".options", extra + ".options", 1)
    return n


AC = "ac dec 40 0.5 3meg\nwrdata {dir}/a.txt vr(out) vi(out)"


def loop_gain(va, pres, res, **kw):
    """T = -v(out)/v(test), loop broken at the speaker end of the feedback arm (Rf, or the shelf
    when there is one). The arm is >= 47 kohm; the 8 ohm tap's source impedance stays under
    about 200 ohm even with no load at these frequencies, so the break does not disturb the loop."""
    an = dict(control=AC, src='ac 0')
    r = nfb.run(netlist(va, pres, res, an, loop_break=True, **kw), ['a'])['a']
    return r[:, 0], -(r[:, 1] + 1j * r[:, 3])


def response(va, pres, res, node='out', **kw):
    an = dict(control=f"ac dec 40 2 200k\nwrdata {{dir}}/a.txt vr({node}) vi({node})")
    r = nfb.run(netlist(va, pres, res, an, **kw), ['a'])['a']
    return r[:, 0], r[:, 1] + 1j * r[:, 3]


def summarize(f, T):
    pms, gm = nfb.margins(f, T)
    lf = [(fc, pm) for fc, pm in pms if fc < 2e3]
    hf = [(fc, pm) for fc, pm in pms if fc >= 2e3]
    # gain margins split into LF and HF (phase through 180 deg below / above 2 kHz)
    gml, gmh = [], []
    for i in range(len(f) - 1):
        if T[i].imag * T[i + 1].imag < 0 and min(T[i].real, T[i + 1].real) < 0:
            t = T[i].imag / (T[i].imag - T[i + 1].imag)
            re = T[i].real + t * (T[i + 1].real - T[i].real)
            if re < 0:
                (gml if f[i] < 2e3 else gmh).append(-20 * np.log10(abs(re)))
    t1k = float(np.interp(3.0, np.log10(f), np.abs(T)))
    return dict(lf=lf, hf=hf, gm=gm, gml=min(gml) if gml else np.inf, gmh=min(gmh) if gmh else np.inf,
                fb1k=20 * np.log10(abs(1 + np.interp(3.0, np.log10(f), T.real)
                                       + 1j * np.interp(3.0, np.log10(f), T.imag))),
                t1k=20 * np.log10(max(t1k, 1e-9)))


TRAN_OPTS = ['method=gear reltol=1e-4', 'method=gear reltol=1e-3 itl4=200 gmin=1e-11',
             'method=trap reltol=1e-3 itl4=200 gmin=1e-11']


def tran(va, vin, tstop, step, nodes, **kw):
    """Transient with the saturating CCS. Writes the raw time points (no linearize: an aborted
    run would come back zero-padded), checks that the run reached tstop, and resamples to a
    uniform grid. Retries with looser solver settings."""
    vecs = ' '.join(f'v({n})' for n in nodes)
    an = dict(vin=vin, control=f"tran {step} {tstop} 0 {step}\nwrdata {{dir}}/w.txt {vecs}")
    last = ''
    for opt in TRAN_OPTS:
        try:
            w = nfb.run(netlist(va, 0.0, 0.0, an, options=opt, ccs_sat=True, **kw), ['w'])['w']
        except RuntimeError as e:
            last = str(e)[-300:]
            continue
        if w.ndim == 2 and w[-1, 0] >= tstop * 0.999 and np.all(np.isfinite(w)):
            t = np.arange(0.0, tstop, step)
            return t, {n: np.interp(t, w[:, 0], w[:, 1 + 2 * i]) for i, n in enumerate(nodes)}
        last = f'stopped at {w[-1, 0] if w.ndim == 2 else "?"} s'
    raise RuntimeError('transient failed: ' + last)
