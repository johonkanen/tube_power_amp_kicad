#!/usr/bin/env python3
"""Rev C bias channel (sheet 02, one OPA462 per tube): ngspice simulations.

Usage:  python3 rev_c/sim/opamp/run_sims.py [item ...]
        items: dc loop step ac pulse powerup loss diss derate   (default: all)

Writes the generated netlists to rev_c/sim/opamp/netlists/, raw ngspice output to
rev_c/sim/opamp/work/ (git-ignored; deleted after reading unless KEEP_WORK=1), plots (PNG) and summary.json
next to this file. A full run takes about 10 minutes.
Model: TI OPA462 PSpice macro-model (rev_c/sim/models/opa462_ti/OPA462.LIB, Final 1.3) run in ngspice with
ngbehavior=ps, wrapped by opa462_ed.lib (E/D pin and low-supply Iq, see that file).
The circuit follows rev_c/tools/sheets/draw_all.py sheet02, channel 1, plus the grid network of sheet 01.
"""
import json
import math
import os
import subprocess
import sys
from itertools import product

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
NET = os.path.join(HERE, "netlists")
WORK = os.path.join(HERE, "work")
TI_LIB = os.path.normpath(os.path.join(HERE, "..", "models", "opa462_ti", "OPA462.LIB"))
ED_LIB = os.path.join(HERE, "opa462_ed.lib")
NGSPICE = os.path.expanduser(os.environ.get("NGSPICE", "~/.local/bin/ngspice"))
os.makedirs(NET, exist_ok=True)
os.makedirs(WORK, exist_ok=True)

LSB = 2.5 / 4096                      # DAC7578 LSB with VREF = 2.5 V
GAIN = 29 * 115 / 125                 # DAC volts -> BIAS volts (26.68)
FS = 4095 * LSB                       # 2.49939 V
SUMMARY = {}


# ------------------------------------------------------------------ netlist
def pwl_ramp(v, t0, tr):
    if t0 <= 0:
        return f"PWL(0 0 {tr:g} {v:g})"
    return f"PWL(0 0 {t0:g} 0 {t0 + tr:g} {v:g})"


def channel(**o):
    """One bias channel with its supplies and the tube grid network.

    Options (defaults in brackets):
      p15 / m80 / p5    source spec for +15 V / -80 V (J201, before the 10R) / +5 V, a SPICE source value string
      rail_mode         'stiff' [default]: sources hold 0 V when off (source and sink);
                        'oneq': +15 V regulator only sources, -80 V only sinks, 10k bleeder when off
      dac               DAC output source value ['DC 0']
      rf, rg, r_in, r_pd  280k, 10k, 10k, 115k
      kref              VREF scale factor [1]
      vos               extra input offset in series with +IN [0]
      cf                Cf [1n];  ro, co: 1k / 1u
      pi                PI plate source value ['DC 280']
      grid_diode        include the grid-cathode diode [True]
      ig                grid (to cathode) current source value [None]
      ilk               leakage into the grid node (gas current, positive into grid) [None]
      break_loop        insert Tian probes Vz / Iz at the op amp output pin [False]
      other_load        model the other three channels + dividers on the rails [True]
    """
    g = dict(p15="DC 15", m80="DC -80", p5="DC 5", rail_mode="stiff", dac="DC 0", rf="280k", rg="10k",
             r_in="10k", r_pd="115k", kref=1.0, vos=0.0, cf="1n", ro="1k", co="1u", pi="DC 280",
             grid_diode=True, ig=None, ilk=None, break_loop=False, other_load=True)
    g.update(o)
    L = []
    a = L.append
    a(f".include {TI_LIB}")
    a(f".include {ED_LIB}")
    a(".options rshunt=1e12")                                # convergence aid (80 pA at 80 V)
    a(".model DS1G D(IS=5n N=1.8 RS=0.05 BV=400)")
    a(".model DGRID D(IS=1n N=2 RS=500)")
    # supplies
    a(f"V15src s15 0 {g['p15']}")
    a(f"V80src s80 0 {g['m80']}")
    a(f"V5src s5 0 {g['p5']}")
    if g["rail_mode"] == "stiff":
        a("R15src s15 p15 0.2")
        a("R80src s80 m80in 0.2")
    else:
        a("B15reg s15 p15 I={max(0, V(s15,p15)) * 5}")      # positive regulator: sources only
        a("R15bl p15 0 10k")
        a("B80reg m80in s80 I={max(0, V(m80in,s80)) * 5}")  # negative regulator: sinks only
        a("R80bl m80in 0 10k")
    a("R5src s5 p5 0.2")
    a("C302 p15 0 10u")
    a("C223 p15 0 100n")
    a("C303 p5 0 10u")
    a("R5load p5 0 1k")                                      # DAC, ADCs, pull-ups on +5 V (about 5 mA)
    # -80 V input (J201 -> R201 10R fusible -> M80; D201 S1G reverse clamp; C201 100u; C202 100n)
    a("R201 m80in m80 10")
    a("D201 m80 0 DS1G")
    a("C201 m80 c201n 100u")
    a("RC201esr c201n 0 0.1")
    a("C202 m80 0 100n")
    a("C224 m80 0 100n")
    if g["other_load"]:
        # the other three OPA462 (3.2 mA Iq + 0.25 mA feedback current each) and about 1.2 mA of dividers etc.,
        # 15 mA in all on -80 V with this channel; scaled to zero as the rails collapse
        a("Bother p15 m80 I={3 * 3.45m * limit(V(p15,m80) / 5, 0, 1)}")
        a("Bextra 0 m80 I={1.2m * limit(-V(m80) / 10, 0, 1)}")
    a("R330 m80 mon 536k")
    a("R331 mon vref 10k")
    a("C331 mon 0 100n")
    # VREF2V5: ADR4525 from +5 V (dropout 0.5 V; nothing below about 1.2 V); C204 1u
    a(f"Bref vri 0 V={{{g['kref']} * limit(V(p5) - 0.5, 0, 2.5) * limit((V(p5) - 1.2) / 0.3, 0, 1)}}")
    a("Rref vri vref 1")
    a("C204 vref 0 1u")
    # DAC -> 10k / 115k || 330n -> +IN
    a(f"VDAC dac 0 {g['dac']}")
    a(f"R210 dac in {g['r_in']}")
    a(f"R211 in 0 {g['r_pd']}")
    a("C210 in 0 330n")
    a(f"Vos in inp DC {g['vos']}")
    # op amp, E/D = +5 V, E/D Com = GND; sense sources on the supply pins
    a("Vsp p15 p15s 0")
    a("Vsm m80 m80s 0")
    a("XU210 inp fb p15s m80s oaout p5 0 OPA462ED")
    if g["break_loop"]:
        a("Vz oa oaout DC 0 AC 0")
        a("Iz 0 oaout DC 0 AC 0")
    else:
        a("Vso oaout oa 0")
    a(f"R212 fb vref {g['rg']}")
    a(f"R213 oa fb {g['rf']}")
    if g["cf"] not in (None, "0", 0):
        if g.get("rcf"):
            a(f"C211 oa cfm {g['cf']}")
            a(f"Rcf cfm fb {g['rcf']}")
        else:
            a(f"C211 oa fb {g['cf']}")
    a(f"R214 oa bias {g['ro']}")
    a(f"C212 bias 0 {g['co']}")
    # tube grid network (sheet 01): PI plate (40k source, 280 V DC) -> 220n -> g1; 91k grid leak BIAS -> g1;
    # 5.6k stopper g1 -> gk; Cgk 15 pF; grid-cathode diode; cathode at GND (1 ohm shunt ignored)
    a(f"Vpi pis 0 {g['pi']}")
    a("Rpi pis pi 40k")
    a("C110 pi g1 220n")
    a("R110 bias g1 91k")
    a("R112 g1 gk 5.6k")
    a("Cgk gk 0 15p")
    if g["grid_diode"]:
        a("Dg gk 0 DGRID")
    if g["ig"]:
        a(f"Igc gk 0 {g['ig']}")
    if g["ilk"]:
        a(f"Ilk 0 gk {g['ilk']}")
    # the macro-model has a second, non-physical DC solution (output beyond V-); steer the operating point
    if g["dac"].startswith("DC") and g["p15"].startswith("DC") and g["m80"].startswith("DC"):
        vd = float(g["dac"].split()[1])
        vin = vd * 115 / 125
        a(f".nodeset v(oa)={GAIN * vd - 70:.4f} v(bias)={GAIN * vd - 70:.4f} v(g1)={GAIN * vd - 70:.4f} "
          f"v(fb)={vin:.4f} v(inp)={vin:.4f} v(in)={vin:.4f} "
          "v(xu210.xu.clamp)=0 v(xu210.xu.vclp)=0 v(xu210.xu.vsense)=0")   # macro-model integrator nodes
    return "\n".join(L)


def _ngspice(path):
    r = subprocess.run([NGSPICE, "-b", "-D", "ngbehavior=ps", path], capture_output=True, text=True, timeout=1800)
    out = r.stdout + r.stderr
    bad = ("simulation(s) aborted" in out or "Timestep too small" in out or "timestep too small" in out
           or "could not be simulated" in out or "source stepping failed" in out)
    return out, bad


OPCHECK = ("op\nlet opcheck_dv = v(inp)-v(fb)\nlet opcheck_rail = v(m80)-v(s80)\n"
           "print opcheck_dv opcheck_rail\n")
SOLVER_NOTES = {}


def _op_ok(out, bad):
    if bad:
        return False
    pv = prints(out)
    dv, dr = pv.get("opcheck_dv"), pv.get("opcheck_rail")
    return dv is not None and abs(dv) < 0.02 and dr is not None and abs(dr) < 2


def _seed(name, body, opts):
    """Operating point of the circuit without the grid diode (which converges more easily; the diode is
    reverse-biased at DC), returned as a .nodeset of every node voltage, to steer the full circuit to it."""
    nb = "\n".join(l for l in body.splitlines() if not l.startswith(("Dg ", ".nodeset")))
    nodes = [l for l in body.splitlines() if l.startswith(".nodeset")]
    path = os.path.join(WORK, name + "_seed.cir")
    for opt in opts:
        for hint in (nodes, []):
            b = "\n".join([nb.replace(".options rshunt=1e12", opt)] + hint)
            with open(path, "w") as f:
                f.write(f"* seed\n{b}\n.control\n{OPCHECK}print all\n.endc\n.end\n")
            out, bad = _ngspice(path)
            if _op_ok(out, bad):
                vals = {k: v for k, v in prints(out).items()
                        if "#" not in k and not k.startswith(("opcheck", "v(", "i(", "@"))}
                return ".nodeset " + "\n+ ".join(f"v({k})={v:.6g}" for k, v in vals.items())
    return None


def run(name, body, control):
    """Write and run a netlist.

    The TI macro-model has a second, non-physical DC solution (output beyond V-, internal integrator nodes at
    1e8 V) that the operating-point solver sometimes lands on, and it occasionally fails the operating point.
    So for netlists with DC supplies (those carry a .nodeset), every run first checks the operating point
    (|V(+IN) - V(-IN)| < 20 mV, i.e. the loop is closed, and the -80 V rail is where its source puts it) and
    retries until it is: (1) as written, (2) seeded with the full operating point of the circuit without the
    grid diode (diode kept), then (3) other solver options, and only last (4) without the grid diode. Runs that
    end up without the diode are recorded in SOLVER_NOTES (summary.json) and checked by the caller."""
    opts = (".options rshunt=1e12", ".options rshunt=1e10", ".options srcsteps=200 gminsteps=200",
            ".options rshunt=1e9 itl1=2000", ".options rshunt=1e12 method=gear",
            ".options rshunt=1e10 method=gear reltol=3e-3 itl4=100")
    has_dc = ".nodeset" in body
    lines = body.splitlines()
    variants = [("as written", body)]
    if has_dc:
        sd = _seed(name, body, opts)
        if sd:
            variants.append(("seeded", "\n".join([l for l in lines if not l.startswith(".nodeset")] + [sd])))
    for opt in opts[1:]:
        variants.append((opt, body.replace(".options rshunt=1e12", opt)))
    nod = "\n".join(l for l in lines if not l.startswith("Dg "))
    for opt in opts:
        variants.append(("NO GRID DIODE " + opt, nod.replace(".options rshunt=1e12", opt)))
    path = os.path.join(NET, name + ".cir")
    for i, (lab, b) in enumerate(variants):
        pre = OPCHECK if has_dc else ""
        with open(path, "w") as f:
            f.write(f"* {name} (generated by run_sims.py)\n{b}\n.control\nset noaskquit\n{pre}{control}\n.endc\n.end\n")
        out, bad = _ngspice(path)
        ok = _op_ok(out, bad) if has_dc else not bad
        if ok:
            if i:
                SOLVER_NOTES[name] = lab
                if lab.startswith("NO GRID DIODE") and "Dg " in body:
                    print(f"  ({name}: ran without the grid diode)")
            return out
    print(out[-3000:])
    raise RuntimeError(f"ngspice failed on {name}")


def wr(name):
    return os.path.join(WORK, name + ".txt")


def load(name, cols):
    """wrdata file with wr_singlescale + wr_vecnames -> dict of columns."""
    d = np.loadtxt(wr(name), skiprows=1)
    if not os.environ.get("KEEP_WORK"):
        os.remove(wr(name))          # raw waveforms are large; KEEP_WORK=1 keeps them in work/
    keys = ["x"] + cols
    return {k: d[:, i] for i, k in enumerate(keys)}


def prints(out):
    vals = {}
    for line in out.splitlines():
        if "=" in line and not line.startswith(("*", "Doing", "Using", "Note", "Reducing")):
            k, _, v = line.partition("=")
            try:
                vals[k.strip()] = float(v.split(",")[0])
            except ValueError:
                pass
    return vals


WRSET = "set wr_singlescale\nset wr_vecnames\noption numdgt=9"


# ------------------------------------------------------------------ 1 DC transfer
def item_dc():
    res = {}
    nom = {}
    for dv, lab in ((0.0, "0"), (1.25, "1.25"), (FS, "FS")):
        out = run(f"dc_nom_{lab}", channel(dac=f"DC {dv}"),
                  "op\nprint v(oa) v(bias) v(inp) v(fb) v(vref) i(vsp) i(vsm) i(vso)")
        p = prints(out)
        ideal = GAIN * dv - 70
        nom[lab] = dict(dac=dv, ideal=ideal, oa=p["v(oa)"], bias=p["v(bias)"], inp=p["v(inp)"],
                        cm_lo=p["v(inp)"] - (-80 + 1), cm_hi=(15 - 3) - p["v(inp)"],
                        sw_lo=p["v(oa)"] - (-80 + 3), sw_hi=(15 - 1.5) - p["v(oa)"])
    res["nominal"] = nom
    # corners: Rf, Rg 0.1 %; VREF 0.02 %; Vos +-3.4 mV (datasheet max, on top of the model's 0.14 mV);
    # V- -78 / -82; +15 V +-5 %; input divider 1 % (only for DAC > 0)
    corners = {}
    for dv, lab in ((0.0, "0"), (1.25, "1.25"), (FS, "FS")):
        vals = []
        div = [(1, 1)] if dv == 0 else list(product((0.99, 1.01), (0.99, 1.01)))
        for (sf, sg, sr, so, vm, vp, (si, sp)) in product((-1, 1), (-1, 1), (-1, 1), (-1, 1), (-78, -82),
                                                        (14.25, 15.75), div):
            body = channel(dac=f"DC {dv}", rf=f"{280e3 * (1 + 1e-3 * sf):.6g}", rg=f"{10e3 * (1 + 1e-3 * sg):.6g}",
                           kref=1 + 2e-4 * sr, vos=3.4e-3 * so, m80=f"DC {vm}", p15=f"DC {vp}",
                           r_in=f"{10e3 * si:.6g}", r_pd=f"{115e3 * sp:.6g}")
            p = prints(run(f"dc_corner", body, "op\nprint v(bias) v(oa)"))
            vals.append((p["v(bias)"], dict(rf=sf, rg=sg, vref=sr, vos=so, vm=vm, vp=vp, rin=si, rpd=sp)))
        lo = min(vals, key=lambda t: t[0])
        hi = max(vals, key=lambda t: t[0])
        corners[lab] = dict(min=lo[0], min_at=lo[1], max=hi[0], max_at=hi[1], n=len(vals))
    res["corners"] = corners
    # grid leakage: 5 uA either way, at DAC 1.25
    lk = {}
    for il in ("5u", "-5u"):
        p = prints(run("dc_leak", channel(dac="DC 1.25", ilk=f"DC {il}", grid_diode=False),
                       "op\nprint v(bias) v(g1) v(oa)"))
        lk[il] = dict(bias=p["v(bias)"], g1=p["v(g1)"], oa=p["v(oa)"])
    res["leak"] = lk
    SUMMARY["dc"] = res
    print(json.dumps(res, indent=1))


# ------------------------------------------------------------------ 2 loop gain
def loop_gain(name, dv=1.25, **o):
    body = channel(dac=f"DC {dv}", break_loop=True, **o)
    ctl = f"""{WRSET}
alter @vz[acmag]=1
ac dec 50 1 100meg
alter @vz[acmag]=0
alter @iz[acmag]=1
ac dec 50 1 100meg
let V1 = ac1.v(oa)
let I1 = -ac1.i(vz)
let V2 = ac2.v(oa)
let I2 = -ac2.i(vz)
let X = I1*V2 - V1*I2
let Tp = 1/(2*X + V1 + I2) - 1
let Tm = 1/(-2*X + V1 + I2) - 1
let trp = real(Tp)
let tip = imag(Tp)
let trm = real(Tm)
let tim = imag(Tm)
wrdata {wr(name)} trp tip trm tim"""
    run(name, body, ctl)
    d = load(name, ["trp", "tip", "trm", "tim"])
    f = d["x"]
    T = d["trp"] + 1j * d["tip"]
    Tm = d["trm"] + 1j * d["tim"]
    return f, T, Tm


def margins(f, T):
    mag = np.abs(T)
    ph = np.degrees(np.unwrap(np.angle(T)))
    ph -= 360 * round(ph[0] / 360)
    idx = np.where((mag[:-1] >= 1) & (mag[1:] < 1))[0]
    if len(idx) == 0:
        return dict(fc=None, pm=None)
    i = idx[-1]
    w = (0 - math.log10(mag[i])) / (math.log10(mag[i + 1]) - math.log10(mag[i]))
    fc = 10 ** (math.log10(f[i]) + w * (math.log10(f[i + 1]) - math.log10(f[i])))
    phc = ph[i] + w * (ph[i + 1] - ph[i])
    pm = 180 + phc
    # gain margin: first -180 crossing after fc
    gm = None
    j = np.where((ph[:-1] > -180) & (ph[1:] <= -180) & (f[:-1] > fc))[0]
    if len(j):
        gm = -20 * math.log10(mag[j[0]])
    # lowest phase margin at any crossing (in case of several)
    pms = []
    for k in idx:
        pms.append(180 + ph[k])
    return dict(fc=fc, pm=pm, gm_db=gm, t_dc=float(mag[0]), pm_all=[float(x) for x in pms],
                min_margin_below_fc=float(np.min(180 + ph[f < fc])) if np.any(f < fc) else None)


def item_loop():
    res = {}
    curves = {}
    cases = [("nominal_dac1.25", dict(dv=1.25)),
             ("nominal_dac0", dict(dv=0.0)),
             ("nominal_dacFS", dict(dv=FS)),
             ("no_grid_network", dict(dv=1.25, grid_diode=False, pi="DC 0")),
             ("Cf_none", dict(dv=1.25, cf=None)),
             ("Cf_100p", dict(dv=1.25, cf="100p")),
             ("Cf_10n", dict(dv=1.25, cf="10n")),
             ("Cf_1n_series_4k7", dict(dv=1.25, rcf="4.7k")),
             ("Cf_1n_series_10k", dict(dv=1.25, rcf="10k")),
             ("Ro_100R", dict(dv=1.25, ro="100")),
             ("Ro_0R_direct_1u", dict(dv=1.25, ro="1m"))]
    for nm, o in cases:
        f, T, Tm = loop_gain("loop_" + nm, **o)
        m = margins(f, T)
        m["tian_cross_term_check_pm"] = margins(f, Tm)["pm"]
        res[nm] = m
        curves[nm] = (f, T)
        print(nm, m)
    SUMMARY["loop"] = res
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7.5, 6), sharex=True)
        for nm, sty in (("nominal_dac1.25", "-"), ("Cf_none", "--"), ("Ro_0R_direct_1u", ":")):
            f, T = curves[nm]
            ph = np.degrees(np.unwrap(np.angle(T)))
            ph -= 360 * round(ph[0] / 360)
            ax1.semilogx(f, 20 * np.log10(np.abs(T)), sty, label=nm.replace("_", " "))
            ax2.semilogx(f, ph, sty)
        ax1.axhline(0, color="0.6", lw=0.8)
        ax2.axhline(-180, color="0.6", lw=0.8)
        ax1.set_ylabel("|T| (dB)")
        ax2.set_ylabel("phase T (deg)")
        ax2.set_xlabel("frequency (Hz)")
        ax1.set_title("Loop gain (Tian), OPA462 TI model, 1k/1uF + grid network")
        ax1.legend(fontsize=8)
        ax1.grid(True, which="both", alpha=0.3)
        ax2.grid(True, which="both", alpha=0.3)
        fig.tight_layout()
        fig.savefig(os.path.join(HERE, "loop_gain.png"), dpi=110)
    except ImportError:
        pass


# ------------------------------------------------------------------ 2b steps
def settle(t, y, t0, final, tol):
    after = t >= t0
    bad = np.where(after & (np.abs(y - final) > tol))[0]
    if len(bad) == 0:
        return 0.0
    return float(t[bad[-1]] - t0)


def item_step():
    res = {}
    vecs = ["v(bias)", "v(oa)", "i(vso)", "v(inp)"]
    names = ["bias", "oa", "io", "inp"]
    # (a) DAC code steps through the input filter
    cases = [("small_up", 1.25, 1.25 + 10 * LSB, 0.12),
             ("large_up", 0.0, FS, 0.3),
             ("large_down", FS, 0.0, 0.3)]
    plots = {}
    for nm, v0, v1, tend in cases:
        body = channel(dac=f"PWL(0 {v0} 10m {v0} 10.001m {v1})")
        ctl = f"{WRSET}\ntran 2u {tend} 0 20u\nwrdata {wr('step_' + nm)} " + " ".join(vecs)
        run("step_" + nm, body, ctl)
        d = load("step_" + nm, names)
        t = d["x"]
        y0 = np.interp(9.9e-3, t, d["bias"])
        y1 = d["bias"][-1]
        step = y1 - y0
        ov = (np.max(d["bias"][t > 10e-3]) - y1) / step * 100 if step > 0 else (np.min(d["bias"][t > 10e-3]) - y1) / step * 100
        ovo = (np.max(d["oa"][t > 10e-3]) - y1) / step * 100 if step > 0 else (np.min(d["oa"][t > 10e-3]) - y1) / step * 100
        dt = np.diff(t)
        sr = np.max(np.abs(np.diff(d["oa"]) / np.where(dt > 0, dt, 1e-12)))
        res[nm] = dict(v_from=y0, v_to=y1, overshoot_bias_pct=ov, overshoot_oa_pct=ovo,
                       settle_1pct_ms=settle(t, d["bias"], 10e-3, y1, abs(step) * 0.01) * 1e3,
                       settle_1lsb_ms=settle(t, d["bias"], 10e-3, y1, GAIN * LSB) * 1e3,
                       io_peak_mA=float(np.max(np.abs(d["io"][t > 10e-3]))) * 1e3,
                       oa_max_slope_V_per_us=sr * 1e-6)
        plots[nm] = d
        print(nm, res[nm])
    # (b) diagnostic: 10 mV step straight at +IN (330n removed, 10 ns edge). With Cf the stage is a unity-gain
    # follower at high frequency, so the edge shows the loop's own ringing (then a slow rise to 29x with
    # Rf.Cf = 280 us). Overshoot = peak above the extrapolated slow ramp / initial jump.
    for nm, o in (("direct_in", {}), ("direct_in_noCf", dict(cf=None))):
        body = channel(dac="DC 1.25", **o).replace("C210 in 0 330n", "C210 in 0 1p")
        body = body.replace("VDAC dac 0 DC 1.25", "VDAC dac 0 PWL(0 1.25 100u 1.25 100.01u 1.26087)")
        run(nm, body, f"{WRSET}\ntran 1n 140u 0 2n\nwrdata {wr(nm)} " + " ".join(vecs))
        d = load(nm, names)
        t = d["x"] - 100e-6
        v0 = np.interp(-1e-6, t, d["oa"])
        w = (t > 4e-6) & (t < 15e-6)
        k = np.polyfit(t[w], d["oa"][w], 1)
        jump = np.polyval(k, 0) - v0
        e = (t > 0) & (t < 4e-6)
        resid = d["oa"][e] - np.polyval(k, t[e])
        settle_i = np.where(np.abs(resid) > 0.01 * abs(jump))[0]
        res[nm] = dict(initial_jump_mV=jump * 1e3, overshoot_pct=float(np.max(resid)) / jump * 100,
                       ring_settle_1pct_us=float(t[e][settle_i[-1]]) * 1e6 if len(settle_i) else 0.0)
        plots[nm] = d
        print(nm, res[nm])
    # (c) load step: 1 mA grid current step (into the cathode) at DAC 1.25
    body = channel(dac="DC 1.25", ig="PULSE(0 1m 10m 1u 1u 1 2)", grid_diode=False)
    run("step_load", body, f"{WRSET}\ntran 1u 60m 0 5u\nwrdata {wr('step_load')} " + " ".join(vecs))
    d = load("step_load", names)
    t = d["x"]
    y0 = np.interp(9.9e-3, t, d["bias"])
    res["load_step_1mA"] = dict(bias_dev_mV=float(np.max(np.abs(d["bias"][t > 10e-3] - y0))) * 1e3,
                                oa_overshoot_check=float(np.max(d["oa"][t > 10e-3]) - np.min(d["oa"][t > 10e-3])))
    print("load", res["load_step_1mA"])
    SUMMARY["step"] = res
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axs = plt.subplots(1, 3, figsize=(11, 3.6))
        d = plots["small_up"]
        axs[0].plot((d["x"] - 10e-3) * 1e3, (d["bias"] - d["bias"][0]) * 1e3, label="BIAS")
        axs[0].plot((d["x"] - 10e-3) * 1e3, (d["oa"] - d["oa"][0]) * 1e3, "--", label="op amp out")
        axs[0].set_title("10-LSB DAC step (1.25 V)")
        axs[0].set_xlabel("ms")
        axs[0].set_ylabel("mV")
        axs[0].legend(fontsize=8)
        for nm in ("large_up", "large_down"):
            d = plots[nm]
            axs[1].plot((d["x"] - 10e-3) * 1e3, d["bias"], label="BIAS " + nm.split("_")[1])
            axs[1].plot((d["x"] - 10e-3) * 1e3, d["oa"], "--", lw=0.8, label="out " + nm.split("_")[1])
        axs[1].set_title("DAC 0 <-> full scale")
        axs[1].set_xlabel("ms")
        axs[1].set_ylabel("V")
        axs[1].legend(fontsize=7)
        for nm, lab in (("direct_in", "Cf 1n (as drawn), PM 48 deg"), ("direct_in_noCf", "no Cf, PM 81 deg")):
            d = plots[nm]
            axs[2].plot((d["x"] - 100e-6) * 1e6, (d["oa"] - d["oa"][0]) * 1e3 / res[nm]["initial_jump_mV"], label=lab)
        axs[2].set_xlim(-0.5, 6)
        axs[2].set_ylim(-0.05, 1.3)
        axs[2].legend(fontsize=8)
        axs[2].set_ylabel("op amp out / initial step")
        axs[2].set_title("loop only: 10 mV step at +IN")
        axs[2].set_xlabel("us")
        for ax in axs:
            ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(os.path.join(HERE, "steps.png"), dpi=110)
    except ImportError:
        pass


# ------------------------------------------------------------------ 3 AC drive coupling, blocking
def item_ac():
    res = {"linear": {}, "with_grid_diode": {}}
    vecs = ["v(bias)", "v(oa)", "i(vso)", "v(g1)", "v(gk)"]
    names = ["bias", "oa", "io", "g1", "gk"]
    for f in (20, 100, 1e3, 20e3):
        for mode, diode in (("linear", False), ("with_grid_diode", True)):
            ncyc = 6 if f >= 100 else 4
            # let the 220n / 91k / 1u settle first: start the sine at 0.3 s (the DC is already there)
            t0 = 0.3
            tend = t0 + ncyc / f + (0.25 if diode else 0.0)
            body = channel(dac="DC 1.25", grid_diode=diode, pi=f"SIN(280 70 {f:g} {t0:g})")
            nm = f"ac_{mode}_{int(f)}"
            step = min(1 / f / 400, 50e-6)
            run(nm, body, f"{WRSET}\ntran {step:g} {tend:g} 0 {step:g}\nwrdata {wr(nm)} " + " ".join(vecs))
            d = load(nm, names)
            t = d["x"]
            last = t > tend - 2 / f
            dt = np.diff(t)
            sl = np.abs(np.diff(d["oa"]) / np.where(dt > 0, dt, 1e-12))
            r = dict(bias_pp_mV=float(np.ptp(d["bias"][last])) * 1e3,
                     bias_mean=float(np.mean(d["bias"][last])),
                     oa_pp_mV=float(np.ptp(d["oa"][last])) * 1e3,
                     io_peak_mA=float(np.max(np.abs(d["io"][t > t0]))) * 1e3,
                     oa_slope_max_V_per_us=float(np.max(sl[t[1:] > t0])) * 1e-6,
                     gk_max=float(np.max(d["gk"][t > t0])),
                     bias_min_after=float(np.min(d["bias"][t > t0])), bias_max_after=float(np.max(d["bias"][t > t0])))
            res[mode][int(f)] = r
            print(mode, f, r)
    # small-signal transfer PI plate -> BIAS, OUT (70 V peak), no grid diode
    body = channel(dac="DC 1.25", grid_diode=False, pi="DC 280 AC 70")
    run("ac_transfer", body, f"{WRSET}\nac dec 20 5 50k\nlet mb = mag(v(bias))\nlet mo = mag(v(oa))\nlet mi = mag(i(vso))\n"
                             f"wrdata {wr('ac_transfer')} mb mo mi")
    d = load("ac_transfer", ["mb", "mo", "mi"])
    res["transfer_70Vpk"] = {f"{fx:g}": dict(bias_pk_mV=float(np.interp(fx, d["x"], d["mb"])) * 1e3,
                                             oa_pk_mV=float(np.interp(fx, d["x"], d["mo"])) * 1e3,
                                             io_pk_mA=float(np.interp(fx, d["x"], d["mi"])) * 1e3)
                             for fx in (20, 50, 100, 1e3, 10e3, 20e3)}
    print(res["transfer_70Vpk"])
    SUMMARY["ac"] = res


def item_pulse():
    res = {}
    vecs = ["v(bias)", "v(oa)", "i(vso)", "v(g1)"]
    names = ["bias", "oa", "io", "g1"]
    for ia, w in product((1e-3, 2e-3, 5e-3), (1e-3, 10e-3)):
        nm = f"pulse_{ia * 1e3:g}mA_{w * 1e3:g}ms"
        body = channel(dac="DC 1.25", grid_diode=False, ig=f"PULSE(0 {ia:g} 20m 10u 10u {w:g} 10)")
        run(nm, body, f"{WRSET}\ntran 5u 0.15 0 10u\nwrdata {wr(nm)} " + " ".join(vecs))
        d = load(nm, names)
        t = d["x"]
        b0 = np.interp(19e-3, t, d["bias"])
        o0 = np.interp(19e-3, t, d["oa"])
        g0 = np.interp(19e-3, t, d["g1"])
        res[nm] = dict(bias_dev_mV=float(np.max(np.abs(d["bias"] - b0))) * 1e3,
                       oa_dev_mV=float(np.max(np.abs(d["oa"] - o0))) * 1e3,
                       io_peak_mA=float(np.max(np.abs(d["io"]))) * 1e3,
                       g1_shift_V=float(np.min(d["g1"] - g0)),
                       g1_back_within_1V_ms=settle(t, d["g1"], 20e-3 + w, g0, 1.0) * 1e3)
        print(nm, res[nm])
    SUMMARY["pulse"] = res


# ------------------------------------------------------------------ 4 power-up
def item_powerup():
    res = {}
    vecs = ["v(bias)", "v(oa)", "v(p15)", "v(m80)", "v(p5)", "v(vref)", "i(vso)"]
    names = ["bias", "oa", "p15", "m80", "p5", "vref", "io"]
    order = {"15": None, "80": None, "5": None}

    def case(nm, t15, t80, t5, tr, mode="stiff", tend=None):
        tend = tend or (max(t15, t80, t5) + tr + 0.6)
        # no HV during power-up: the PI plate (driver B+) is at 0 V; its arrival is a separate case below
        body = channel(dac="DC 0", rail_mode=mode, p15=pwl_ramp(15, t15, tr), m80=pwl_ramp(-80, t80, tr),
                       p5=pwl_ramp(5, t5, tr), pi="DC 0")
        run("pu_" + nm, body, f"{WRSET}\ntran 20u {tend:g} 0 50u uic\nwrdata {wr('pu_' + nm)} " + " ".join(vecs))
        d = load("pu_" + nm, names)
        t = d["x"]
        tall = max(t15, t80, t5) + tr
        i_max = int(np.argmax(d["bias"]))
        above = np.where(d["bias"] > -20)[0]
        cold = settle(t, d["bias"], 0, -70.0, 0.5)
        r = dict(t15=t15, t80=t80, t5=t5, ramp=tr, mode=mode,
                 bias_max=float(d["bias"][i_max]), t_bias_max_ms=float(t[i_max]) * 1e3,
                 oa_max=float(np.max(d["oa"])),
                 time_above_0V_ms=float(np.sum(np.diff(t)[d["bias"][1:] > 0])) * 1e3,
                 last_above_m20_ms=float(t[above[-1]]) * 1e3 if len(above) else 0.0,
                 within_0p5V_of_cold_ms=cold * 1e3, all_rails_up_ms=tall * 1e3,
                 p15_min=float(np.min(d["p15"])), m80_max=float(np.max(d["m80"])),
                 bias_final=float(d["bias"][-1]))
        res[nm] = r
        print(nm, r)
        return d

    tr = 10e-3
    st = 0.1
    keep = {}
    for perm in (("15", "80", "5"), ("80", "15", "5"), ("15", "5", "80"), ("5", "15", "80"), ("80", "5", "15"),
                 ("5", "80", "15")):
        tt = {k: i * st for i, k in enumerate(perm)}
        nm = "order_" + "_".join(perm) + "_10ms"
        keep[nm] = case(nm, tt["15"], tt["80"], tt["5"], tr)
    keep["together_10ms"] = case("together_10ms", 0, 0, 0, tr)
    keep["together_200ms"] = case("together_200ms", 0, 0, 0, 0.2)
    case("slow_15_80_5_200ms", 0, 0.1, 0.2, 0.2)
    case("slow_80_15_5_200ms", 0.1, 0, 0.2, 0.2)
    case("slow_5_15_80_200ms", 0.1, 0.2, 0, 0.2)
    case("slow_15_5_80_200ms", 0, 0.2, 0.1, 0.2)
    # off rails high impedance (regulators source / sink only, 10k bleeders)
    keep["oneq_15_80_5"] = case("oneq_order_15_80_5_10ms", 0, st, 2 * st, tr, mode="oneq")
    case("oneq_order_80_15_5_10ms", st, 0, 2 * st, tr, mode="oneq")
    case("oneq_order_5_80_15_10ms", 2 * st, st, 0, tr, mode="oneq")
    case("oneq_together_10ms", 0, 0, 0, tr, mode="oneq")
    # driver B+ (PI plate 0 -> 280 V) arriving after the bias is up: 10 ms and 1 ms ramps at t = 0.4 s
    for trp in (10e-3, 1e-3):
        nm = f"pi_bplus_{trp * 1e3:g}ms"
        body = channel(dac="DC 0", p15=pwl_ramp(15, 0, 10e-3), m80=pwl_ramp(-80, 0, 10e-3), p5=pwl_ramp(5, 0, 10e-3),
                       pi=f"PWL(0 0 0.4 0 {0.4 + trp:g} 280)")
        run(nm, body, f"{WRSET}\ntran 10u 0.6 0 20u uic\nwrdata {wr(nm)} " + " ".join(vecs))
        d = load(nm, names)
        t = d["x"]
        b0 = np.interp(0.39, t, d["bias"])
        sel = t > 0.4
        res[nm] = dict(bias_before=float(b0), bias_max_after=float(np.max(d["bias"][sel])),
                       excursion_V=float(np.max(d["bias"][sel]) - b0), io_peak_mA=float(np.max(np.abs(d["io"][sel]))) * 1e3)
        print(nm, res[nm])
    SUMMARY["powerup"] = res
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(8, 4.2))
        for nm in ("order_15_80_5_10ms", "order_15_5_80_10ms", "order_80_15_5_10ms", "order_80_5_15_10ms",
                   "order_5_15_80_10ms", "together_200ms"):
            d = keep[nm]
            ax.plot(d["x"] * 1e3, d["bias"], label=nm.replace("_", " "))
        ax.axhline(0, color="0.5", lw=0.8)
        ax.set_xlabel("ms")
        ax.set_ylabel("BIASn (V)")
        ax.set_title("Power-up, DAC held at 0 (rails staggered 100 ms, 10 ms ramps unless noted)")
        ax.legend(fontsize=7)
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(os.path.join(HERE, "powerup.png"), dpi=110)
    except ImportError:
        pass


# ------------------------------------------------------------------ 5 loss of -80 V
def item_loss():
    res = {}
    vecs = ["v(bias)", "v(oa)", "v(m80)", "v(p15)"]
    names = ["bias", "oa", "m80", "p15"]
    for dv, lab in ((0.0, "dac0"), (1.25, "dac1.25")):
        for mode, src in (("open", None), ("to0V_fast", "PWL(0 -80 50m -80 51m 0)")):
            nm = f"loss_{lab}_{mode}"
            if mode == "open":
                # J201 source disconnects at 50 ms: modelled as the source going high impedance
                body = channel(dac=f"DC {dv}").replace("R80src s80 m80in 0.2",
                                                        "S80 s80 m80in ctl 0 SWOPEN\nVctl ctl 0 PWL(0 1 50m 1 50.01m 0)\n"
                                                        ".model SWOPEN SW(VT=0.5 VH=0.1 RON=0.2 ROFF=1e9)")
            else:
                body = channel(dac=f"DC {dv}", m80=src)
            run(nm, body, f"{WRSET}\ntran 50u 1.5 0 200u\nwrdata {wr(nm)} " + " ".join(vecs))
            d = load(nm, names)
            t = d["x"]
            b0 = np.interp(40e-3, t, d["bias"])
            def first(cond):
                i = np.where(cond & (t > 50e-3))[0]
                return float(t[i[0]] - 50e-3) * 1e3 if len(i) else None
            res[nm] = dict(bias_before=b0, t_bias_moves_0p5V_ms=first(d["bias"] > b0 + 0.5),
                           t_bias_above_m20_ms=first(d["bias"] > -20),
                           t_bias_above_m10_ms=first(d["bias"] > -10),
                           t_bias_above_0_ms=first(d["bias"] > 0), bias_max=float(np.max(d["bias"])),
                           t_rail_m70_ms=first(d["m80"] > -70),
                           bias_final=float(d["bias"][-1]), m80_final=float(d["m80"][-1]))
            print(nm, res[nm])
    # informational: loss of +5 V (VREF2V5 and E/D go with it) or of +15 V, the other rails present, DAC 1.25 V
    for nm, kw in (("loss_p5_dac1.25_dac_held", dict(p5="PWL(0 5 50m 5 51m 0)")),
                   ("loss_p5_dac1.25_dac_to_0", dict(p5="PWL(0 5 50m 5 51m 0)", dac="PWL(0 1.25 50m 1.25 51m 0)")),
                   ("loss_p15_dac1.25", dict(p15="PWL(0 15 50m 15 51m 0)"))):
        kw.setdefault("dac", "DC 1.25")
        body = channel(**kw)
        run(nm, body, f"{WRSET}\ntran 50u 1.5 0 200u\nwrdata {wr(nm)} " + " ".join(vecs))
        d = load(nm, names)
        t = d["x"]
        b0 = np.interp(40e-3, t, d["bias"])

        def first(cond):
            i = np.where(cond & (t > 50e-3))[0]
            return float(t[i[0]] - 50e-3) * 1e3 if len(i) else None
        res[nm] = dict(bias_before=b0, t_bias_moves_0p5V_ms=first(np.abs(d["bias"] - b0) > 0.5),
                       t_bias_above_m20_ms=first(d["bias"] > -20), t_bias_above_m10_ms=first(d["bias"] > -10),
                       bias_max=float(np.max(d["bias"][t > 50e-3])), bias_min=float(np.min(d["bias"][t > 50e-3])),
                       bias_final=float(d["bias"][-1]))
        print(nm, res[nm])
    SUMMARY["loss"] = res


# ------------------------------------------------------------------ 6 dissipation
def item_diss():
    res = {}
    for vm, vp, dv in product((-78, -82), (14.25, 15.75), (0.0, FS)):
        out = run("diss", channel(dac=f"DC {dv}", m80=f"DC {vm}", p15=f"DC {vp}"),
                  "op\nprint v(p15) v(m80) v(oa) i(vsp) i(vsm) i(vso)")
        p = prints(out)
        pw = p["v(p15)"] * p["i(vsp)"] + p["v(m80)"] * p["i(vsm)"] - p["v(oa)"] * p["i(vso)"]
        res[f"Vm{vm}_Vp{vp}_dac{dv:.2f}"] = dict(P_mW=pw * 1e3, iq_p_mA=p["i(vsp)"] * 1e3, iq_m_mA=-p["i(vsm)"] * 1e3,
                                                  P_Iqmax_mW=(p["v(p15)"] - p["v(m80)"]) * 3.7
                                                  + (pw * 1e3 - (p["v(p15)"] - p["v(m80)"]) * 3.2))
    # with the 70 V-peak drive at 20 Hz (op amp output current about 0.5 mA peak), from transient
    body = channel(dac="DC 1.25", m80="DC -82", p15="DC 15.75", grid_diode=False, pi="SIN(280 70 20 0.3)")
    run("diss_ac", body, f"{WRSET}\ntran 50u 0.5 0 50u\nlet pw = v(p15)*i(vsp) + v(m80)*i(vsm) - v(oa)*i(vso)\n"
                         f"wrdata {wr('diss_ac')} pw")
    d = load("diss_ac", ["pw"])
    sel = d["x"] > 0.4
    res["ac_20Hz_70Vpk_Vm-82_Vp15.75"] = dict(P_mW=float(np.trapezoid(d["pw"][sel], d["x"][sel]) / np.ptp(d["x"][sel])) * 1e3)
    for k, v in res.items():
        print(k, v)
    SUMMARY["diss"] = res


def item_derate():
    """C2n2 (1 uF / 100 V X7R 0805) loses most of its capacitance at 70 V DC bias: rerun the drive coupling
    transfer and the loop gain with 0.25 uF."""
    res = {}
    body = channel(dac="DC 0", grid_diode=False, pi="DC 280 AC 70", co="0.25u")
    run("derate_transfer", body, f"{WRSET}\nac dec 20 5 50k\nlet mb = mag(v(bias))\nlet mi = mag(i(vso))\n"
                                 f"wrdata {wr('derate_transfer')} mb mi")
    d = load("derate_transfer", ["mb", "mi"])
    res["transfer_70Vpk_Co_0.25u"] = {f"{fx:g}": dict(bias_pk_mV=float(np.interp(fx, d["x"], d["mb"])) * 1e3,
                                                      io_pk_mA=float(np.interp(fx, d["x"], d["mi"])) * 1e3)
                                      for fx in (20, 100, 1e3, 10e3, 20e3)}
    f, T, _ = loop_gain("loop_derate_Co_0.25u", dv=0.0, co="0.25u")
    res["loop_Co_0.25u"] = margins(f, T)
    print(res)
    SUMMARY["derate"] = res


ITEMS = dict(dc=item_dc, loop=item_loop, step=item_step, ac=item_ac, pulse=item_pulse, powerup=item_powerup,
             loss=item_loss, diss=item_diss, derate=item_derate)

if __name__ == "__main__":
    todo = sys.argv[1:] or list(ITEMS)
    sj = os.path.join(HERE, "summary.json")
    if os.path.exists(sj):
        SUMMARY.update(json.load(open(sj)))
    for it in todo:
        print(f"===== {it}")
        ITEMS[it]()
        SUMMARY.setdefault("solver_notes", {}).update(SOLVER_NOTES)
        with open(sj, "w") as f:
            json.dump(SUMMARY, f, indent=1, default=float)
