"""Phase inverter + power stage + negative feedback with presence and resonance (simulation plan
2b.3, Q7). Netlist builder and ngspice runner.

Chain: source (Rs) -> 22n -> long-tailed pair PI (12AX7) -> the push-pull power stage of
sim/power_stage (4 tubes, 0.1u / 220k / own bias source, 1650TA) -> speaker model -> feedback
network -> PI.

Feedback network (our own starting values, to be tuned):

    out (8 ohm tap) ──(Rf ‖ Cf)──X──(Cres ‖ Pres)──F (feedback node)──Rbot── gnd
                                                    └── rpmin ── Pp (presence, rheostat) ── Cp ── gnd

- Presence: Pp + Cp shunt F at high frequencies, removing feedback there (treble rises).
  Presence 100 % = Pp at 0 ohm.
- Resonance: at low frequencies Cres blocks the feedback unless Pres shorts it. Resonance 0 % =
  Pres at 0 ohm (full feedback at all frequencies); 100 % = Pres at its full value.

Injection into the PI:
- 'grid2': the second triode's grid is AC-coupled (100n) to F; the tail returns to ground.
- 'tail':  Marshall/Fender style; the tail returns to F, and the second grid is AC-grounded.
"""
import os
import re
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', 'power_stage')))
import stage  # noqa: E402

PI_DEFAULTS = dict(bplus=390.0, ra1=82e3, ra2=100e3, rk=1e3, rtail=10e3, rgl=1e6, cin=22e-9,
                   cg2=100e-9, rs=10e3, tube='12AX7_DZ')
NFB_DEFAULTS = dict(rf=100e3, rbot=4.7e3,
                    pp=50e3, pp_taper='rlog', rpmin=1e3, cp=22e-9,      # presence
                    pres=250e3, pres_taper='log', cres=22e-9,           # resonance
                    cf=22e-12)                                         # HF compensation across Rf
# Chosen by run_nfb.py (2026-11-19): Rf 100k (about 6 dB of feedback) with Cf 22p keeps the
# phase margin near or above 45 deg even with an assumed 0.5-1 nF of OT primary capacitance;
# Cp 22n starts the presence boost near 2.5-4 kHz; rpmin 1k limits it to a shelf; the pot values
# and tapers spread each control over its rotation.

# Representative 8 ohm guitar speaker (not a measured cab): Re, voice-coil inductance with eddy
# loss, and the cone resonance as a parallel RLC: about 46 ohm peak at 95 Hz, Q about 3.4.
SPEAKER = dict(re=6.4, le=0.7e-3, rle=30.0, rm=40.0, lm=19.5e-3, cm=144e-6)

EL34_SET = ['EL34'] * 4
IDLE_IA = 0.044          # constant idle current per tube (bias law, sim/power_stage): 70 % Pa at 400 V


def vg2_for(va, tubes=EL34_SET):
    """V_SCREEN follows V_ANODE, held at the per-type setpoint (D13: about 370 V for EL34)."""
    return min(va, 370.0)


_bias_cache = {}


def bias_for(va, tubes=EL34_SET):
    key = (va, tuple(tubes))
    if key not in _bias_cache:
        r = stage.solve_bias(tubes, va, 'B', vg2_for(va, tubes), ('ia', [IDLE_IA] * 4))
        _bias_cache[key] = r['vg1']
    return _bias_cache[key]


def pot_pos(x, total, taper='lin'):
    if taper == 'log':                     # audio taper, 10 % at mid rotation
        x = (81.0 ** x - 1.0) / 80.0
    elif taper == 'rlog':                  # reverse audio taper (C), 90 % at mid rotation
        x = 1.0 - (81.0 ** (1.0 - x) - 1.0) / 80.0
    return max(total * x, 1.0)


def netlist(va, presence, resonance, analysis, mode='grid2', load='speaker', pol=1, nfb=True,
            tubes=EL34_SET, pi=None, net=None, loop_break=False,
            options='method=gear reltol=1e-4', stage_p=None):
    """presence, resonance: 0..1. pol: +1 or -1 swaps which PI plate drives which side, so the
    feedback can be made negative. loop_break: feed Rf from a test source instead of the
    speaker (for the loop gain)."""
    P = dict(PI_DEFAULTS, **(pi or {}))
    N = dict(NFB_DEFAULTS, **(net or {}))
    base = stage.netlist(tubes, va, 'B', vg2_for(va, tubes), 0.0, bias_for(va, tubes), p=stage_p)
    keep = []
    for line in base.split('\n'):
        if line.startswith('.control'):
            break
        if line.split(' ')[0] in ('Bpi1', 'Bpi2', 'Rpi1', 'Rpi2', 'Rload'):
            continue
        keep.append(line)
    n = '\n'.join(keep) + '\n'
    # speaker / load on the 8 ohm tap (node out)
    if load == 'speaker':
        s = SPEAKER
        n += (f"Rre out sp1 {s['re']}\nLle sp1 sp2 {s['le']}\nRle sp1 sp2 {s['rle']}\n"
              f"Rrm sp2 0 {s['rm']}\nLlm sp2 0 {s['lm']}\nCcm sp2 0 {s['cm']}\n")
    else:
        n += "Rload out 0 8\n"
    # PI: long-tailed pair
    o_inv, o_non = ('o1', 'o2') if pol > 0 else ('o2', 'o1')
    tail_bot = 'fnode' if mode == 'tail' else '0'
    g2ret = 'fnode' if mode == 'grid2' else '0'
    n += (f"Vpi pi_bp 0 {P['bplus']}\n"
          + (analysis['vin'] + "\n" if 'vin' in analysis else
             f"Vin pi_src 0 dc 0 {analysis.get('src', 'ac 1')}\n") +
          f"Rsrc pi_src pi_s1 {P['rs']}\nCin pi_s1 pi_gx {P['cin']}\n"
          f"Rg1 pi_gx pi_top {P['rgl']}\nRstp pi_gx pi_g1 {P.get('rstop', 1.0)}\n"
          f"Rg2 pi_g2 pi_top {P['rgl']}\nCg2 pi_g2 {g2ret} {P['cg2']}\n"
          f"XP1 pi_p1 pi_g1 pi_k {P['tube']}\nXP2 pi_p2 pi_g2 pi_k {P['tube']}\n"
          f"Rpa1 pi_bp pi_p1 {P['ra1']}\nRpa2 pi_bp pi_p2 {P['ra2']}\n"
          f"Rpk pi_k pi_top {P['rk']}\n"
          + (f"Itail pi_top {tail_bot} {P['ccs']}\nRtail pi_top {tail_bot} 10meg\n" if P.get('ccs')
             else f"Rtail pi_top {tail_bot} {P['rtail']}\n") +
          f"Vo1 pi_p1 {o_inv} 0\nVo2 pi_p2 {o_non} 0\n")
    if P.get('cpp'):                      # PI plate-to-plate compensation cap
        n += f"Cpp pi_p1 pi_p2 {P['cpp']}\n"
    # feedback network
    fb_from = 'vtest' if loop_break else 'out'
    if loop_break:
        n += "Vt vtest 0 dc 0 ac 1\n"
    n += f"Rbot fnode 0 {N['rbot']}\n"
    if nfb:
        if N.get('cf'):
            n += f"Cf {fb_from} fx {N['cf']}\n"
        n += (f"Rf {fb_from} fx {N['rf']}\nCres fx fnode {N['cres']}\n"
              f"Rres fx fnode {pot_pos(resonance, N['pres'], N.get('pres_taper', 'lin'))}\n"
              f"Rpp fnode fp {N['pp'] - pot_pos(presence, N['pp'], N.get('pp_taper', 'lin')) + 1.0 + N.get('rpmin', 0.0)}\n"
              f"Cp fp 0 {N['cp']}\n")
    if N.get('cstep'):                    # fixed step (lag-lead) network: F -> rstep -> cstep -> gnd
        n += f"Rstep fnode fst {N['rstep']}\nCstep fst 0 {N['cstep']}\n"
    if N.get('czob'):                     # Zobel across the 8 ohm tap
        n += f"Rzob out zb {N['rzob']}\nCzob zb 0 {N['czob']}\n"
    if N.get('cot'):                      # assumed OT primary capacitance, each half to the centre tap
        n += f"Cota pa ct {N['cot']}\nCotb pb ct {N['cot']}\n"
    n += f".options {options}\n"
    n += ".control\n" + analysis['control'] + "\n.endc\n.end\n"
    return n


def run(net, keys):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, 'b.cir')
        with open(p, 'w') as f:
            f.write(net.replace('{dir}', d))
        r = subprocess.run(['ngspice', '-b', p], capture_output=True, text=True, timeout=900)
        out = {}
        for k in keys:
            fp = os.path.join(d, k + '.txt')
            if not os.path.exists(fp):
                raise RuntimeError(f"no {k}:\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}")
            out[k] = np.loadtxt(fp)
        return out


AC = "ac dec 30 5 2meg\nwrdata {dir}/a.txt vr(%s) vi(%s)"


def response(va, presence, resonance, node='out', **kw):
    """Complex closed-loop transfer from the source to `node`."""
    r = run(netlist(va, presence, resonance, dict(control=AC % (node, node)), **kw), ['a'])['a']
    return r[:, 0], r[:, 1] + 1j * r[:, 3]


def loop_gain(va, presence, resonance, **kw):
    """Return ratio T = -v(out)/v(test) with the loop broken at the speaker end of Rf (a
    low-impedance node driving a high-impedance one, so the break doesn't disturb loading).
    Negative feedback: T is positive real in the midband."""
    an = dict(control=AC % ('out', 'out'), src='ac 0')
    r = run(netlist(va, presence, resonance, an, loop_break=True, **kw), ['a'])['a']
    return r[:, 0], -(r[:, 1] + 1j * r[:, 3])


def margins(f, T):
    """Phase margin at every unity crossing of |T| (180 deg minus |wrapped phase of T|), and
    the gain margin: -|T| in dB where the phase of T passes through 180 deg (T real and
    negative), worst case. T is positive real where the feedback is negative."""
    mag = np.abs(T)
    ph = np.degrees(np.angle(T))           # wrapped to (-180, 180]
    pms = []
    for i in range(len(f) - 1):
        if (mag[i] - 1) * (mag[i + 1] - 1) < 0:
            t = (1 - mag[i]) / (mag[i + 1] - mag[i])
            fc = f[i] * (f[i + 1] / f[i]) ** t
            Tc = T[i] + t * (T[i + 1] - T[i])
            pms.append((fc, 180.0 - abs(np.degrees(np.angle(Tc)))))
    gms = []
    for i in range(len(f) - 1):
        if T[i].imag * T[i + 1].imag < 0 and min(T[i].real, T[i + 1].real) < 0:
            t = T[i].imag / (T[i].imag - T[i + 1].imag)
            re = T[i].real + t * (T[i + 1].real - T[i].real)
            if re < 0:
                gms.append(-20 * np.log10(abs(re)))
    gm = min(gms) if gms else float('inf')
    return pms, gm


def find_polarity(va=400.0, **kw):
    """+1 or -1, whichever makes the feedback negative (T positive real at 1 kHz)."""
    f, T = loop_gain(va, 0.0, 0.0, pol=1, **kw)
    t1k = T[np.argmin(abs(f - 1000))]
    return 1 if t1k.real > 0 else -1
