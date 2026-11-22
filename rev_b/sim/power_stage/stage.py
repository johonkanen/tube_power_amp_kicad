"""Push-pull power stage netlist generator and ngspice runner (simulation plan, section 1).

Circuit (per simulation_plan.md 1.2):
- 4 output tubes, two per side, each with its own coupling cap, grid leak to its own bias
  source (PA-2), grid stopper, 1 ohm cathode shunt (PA-4) and screen resistor.
- PI outputs as antiphase sources with an output impedance and a soft clip limit.
- Hammond 1650TA: coupled-inductor model from the datasheet (Lp, leakage, DCR).
- Screen supply option A (from V_ANODE through a dropper) or B (separate V_SCREEN).

Two runs per case:
1. DC operating point with a behavioural servo on each bias source, which finds the Vg1 that
   gives the idle plate dissipation target. ngspice solves the servo loop in the op.
2. Transient with the bias sources fixed at the values found in step 1.
"""
import os
import re
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.normpath(os.path.join(HERE, '..', 'models', 'tubes.lib'))

# Tube ratings: design-centre maximums from the datasheets (verify before quoting as limits).
# pa: plate dissipation W, pg2: screen dissipation W, vg2: max screen voltage V, va: max plate V
TUBES = {
    'EL34':  dict(model='EL34_R',  pa=25.0, pg2=8.0, vg2=425.0, va=800.0),
    '6L6GC': dict(model='6L6GC_R', pa=30.0, pg2=5.0, vg2=450.0, va=500.0),
    '6550':  dict(model='6550_X',  pa=42.0, pg2=6.0, vg2=400.0, va=600.0),   # RCA 1962: Pa 35 W; reissues 42 W
    'KT88':  dict(model='KT88_X',  pa=42.0, pg2=8.0, vg2=600.0, va=800.0),
}
# Models: section 0 of the simulation plan (sim/models/README.md). EL34_R, 6L6GC_R: Reefman's
# measured uTracer fits. KT88_X, 6550_X: our datasheet fits. Koren *_K models no longer used.
# Errors from the push-pull bench (sim/models/pushpull_results.md), full signal vs datasheet:
#   screen current EL34 +5%, 6550 -5..-8%, KT88 -30%, 6L6GC -42%; power EL34 +29%, 6L6GC -10%,
#   KT88 -23%, 6550 -15..-18%.

# Hammond 1650TA (datasheet): 1.9k plate-to-plate, Lp 11.2 H, leakage 63.72 mH, DCR 47 ohm,
# secondary DCR 0.294 ohm on the 8 ohm tap.
OT = dict(raa=1900.0, lp=11.2, lleak=63.72e-3, rpri=47.0, rsec=0.294, rl=8.0)

DEFAULTS = dict(
    rout_pi=10e3,      # PI output impedance per side
    vclip_pi=80.0,     # PI soft clip, V peak per side
    cc=0.1e-6,         # coupling cap per tube
    rgl=220e3,         # grid leak per tube
    rstop=5.6e3,       # grid stopper
    rk=1.0,            # cathode current shunt
    rg2=1e3,           # screen resistor per tube
    rdrop=1e3,         # option A: common screen dropper from V_ANODE
    rsupply=5.0,       # V_ANODE / V_SCREEN source impedance
    csupply=100e-6,    # reservoir at the centre tap and screen node
    f=1000.0,
)


def ot_values(load_factor=1.0):
    lhalf = OT['lp'] / 4.0                      # coupled halves: Lp = 4 * Lhalf
    lsec = OT['lp'] * OT['rl'] / OT['raa']      # secondary for the 8 ohm tap
    k = (1.0 - OT['lleak'] / OT['lp']) ** 0.5
    return lhalf, lsec, k, OT['rl'] * load_factor


def netlist(tubes, va, screen, vg2_b, drive, bias=None, idle_frac=0.7, p=None, ac=None):
    """tubes: 4 tube type names, tubes 0,1 on side A (plate node pa), 2,3 on side B.
    screen: 'A' (dropper from V_ANODE) or 'B' (separate supply at vg2_b).
    bias: list of 4 fixed Vg1 values, or None to solve them with the DC servo. The servo target
        is idle_frac: a number (fraction of Pa max) or ('ia', [4 plate currents in A]).
    drive: PI drive amplitude, V peak per side before the soft clip.
    ac: None for a transient, or a list of tube indices whose bias source carries AC 1 V
        (the bias-noise gain from the bias source to the speaker)."""
    q = dict(DEFAULTS, **(p or {}))
    lhalf, lsec, k, rl = ot_values(q.get('load_factor', 1.0))
    L = [f'* push-pull power stage {tubes} Va={va} screen={screen}',
         f'.include "{LIB}"',
         f'.param vclip={q["vclip_pi"]} amp={drive} f={q["f"]}',
         # supplies
         f'Vanode vas 0 {va}',
         f'Rsa vas ct {q["rsupply"]}',
         f'Csa ct 0 {q["csupply"]}',
         ]
    if screen == 'A':
        L += [f'Rdrop ct sg {q["rdrop"]}', f'Csg sg 0 {q["csupply"]}']
    else:
        L += [f'Vscreen vss 0 {vg2_b}', f'Rss vss sg {q["rsupply"]}', f'Csg sg 0 {q["csupply"]}']
    # output transformer: halves ct-pa and ct-pb, DCR per half
    L += [f'Rpa ct ta {OT["rpri"] / 2}', f'L1 ta pa {lhalf}',
          f'Rpb ct tb {OT["rpri"] / 2}', f'L2 pb tb {lhalf}',  # dot at the plate end: halves in push-pull
          f'L3 sx 0 {lsec}', f'Rsec sx out {OT["rsec"]}',
          f'K12 L1 L2 {k}', f'K13 L1 L3 {k}', f'K23 L2 L3 {k}']
    if q.get('cpp'):
        # primary self-capacitance, plate to plate (not in the datasheet: an assumption)
        L.append(f'Cpp pa pb {q["cpp"]}')
    if q.get('load_net'):
        # load netlist between the nodes out and 0 (e.g. a speaker impedance model)
        L.append(q['load_net'])
    elif rl is not None and rl > 0 and q.get('load_factor', 1.0) < 1e3:
        L.append(f'Rload out 0 {rl}')
    else:
        L.append('Rload out 0 1e6')
    # PI: antiphase soft-clipped sources with output impedance
    if q.get('driver'):
        # external driver netlist (a real phase inverter, master volume...) that defines the
        # nodes o1 and o2 feeding the per-tube coupling caps; it may use {amp} and {f}
        L += [q['driver']]
    else:
        L += ['Bpi1 d1 0 V = {vclip*tanh(amp*sin(2*pi*f*time)/vclip)}',
              'Bpi2 d2 0 V = {-vclip*tanh(amp*sin(2*pi*f*time)/vclip)}',
              f'Rpi1 d1 o1 {q["rout_pi"]}', f'Rpi2 d2 o2 {q["rout_pi"]}']
    for i, t in enumerate(tubes):
        n = i + 1
        side = 'pa' if i < 2 else 'pb'
        drv = 'o1' if i < 2 else 'o2'
        pamax = TUBES[t]['pa']
        if bias is None:
            if isinstance(idle_frac, tuple):
                # servo on plate current (constant-current bias law)
                L.append(f'Bb{n} b{n} 0 V = {{min(0, max(-200, -1e5*(I(Vsa{n}) - {idle_frac[1][i]})))}}')
            else:
                # servo: drive the bias source until plate dissipation = idle_frac * Pa max
                L.append(f'Bb{n} b{n} 0 V = {{min(0, max(-200, -2e4*(V(a{n},k{n})*I(Vsa{n}) - {idle_frac * pamax})))}}')
        else:
            acs = ' AC 1' if ac and i in ac else ''
            L.append(f'Vb{n} b{n} 0 DC {bias[i]}{acs}')
        L += [f'Cc{n} {drv} gl{n} {q["cc"]}',
              f'Rgl{n} gl{n} b{n} {q["rgl"]}',
              f'Rst{n} gl{n} g{n} {q["rstop"]}',
              f'Vsa{n} {side} a{n} 0',
              f'Rg2{n} sg s{n} {q["rg2"]}',
              f'Vss{n} s{n} s{n}x 0',
              f'X{n} a{n} s{n}x g{n} k{n} {TUBES[t]["model"]}',
              f'Rk{n} k{n} 0 {q["rk"]}',
              f'Bpa{n} pa{n} 0 V = {{V(a{n},k{n})*I(Vsa{n})}}',
              f'Bpg{n} pg{n} 0 V = {{V(s{n}x,k{n})*I(Vss{n})}}',
              f'Bov{n} ov{n} 0 V = {{V(s{n}x) - V(a{n})}}']
    L.append('.options method=gear reltol=1e-4 itl1=500 itl4=200')
    if bias is None:
        prints = ' '.join([f'v(b{n})' for n in range(1, 5)] +
                          [f'v(a{n})' for n in range(1, 5)] +
                          [f'v(s{n}x)' for n in range(1, 5)] +
                          [f'i(Vsa{n})' for n in range(1, 5)] +
                          [f'i(Vss{n})' for n in range(1, 5)])
        L += ['.control', 'op', f'print {prints}', '.endc', '.end']
    elif ac:
        L += ['.control', 'ac dec 20 10 100k'] + \
             [f'meas ac g{int(fr)} FIND vm(out) AT={fr}' for fr in (100, 1000, 10000)] + \
             ['.endc', '.end']
    else:
        t0, t1 = 60e-3, 65e-3
        meas = [f'meas tran vrms RMS v(out) from={t0} to={t1}',
                f'meas tran ianode AVG i(Vanode) from={t0} to={t1}',
                f'meas tran ianodepk MIN i(Vanode) from={t0} to={t1}']
        if screen == 'B':
            meas += [f'meas tran iscreen AVG i(Vscreen) from={t0} to={t1}']
        for n in range(1, 5):
            meas += [f'meas tran vgmax{n} MAX v(g{n}) from={t0} to={t1}']
            meas += [f'meas tran pa{n} AVG v(pa{n}) from={t0} to={t1}',
                     f'meas tran pg{n} AVG v(pg{n}) from={t0} to={t1}',
                     f'meas tran ig2pk{n} MAX i(Vss{n}) from={t0} to={t1}',
                     f'meas tran ov{n} MAX v(ov{n}) from={t0} to={t1}',
                     f'meas tran vgavg{n} AVG v(gl{n}) from={t0} to={t1}',
                     f'meas tran iapk{n} MAX i(Vsa{n}) from={t0} to={t1}']
        L += ['.control', 'set nfreqs=10', f'tran 2u {t1} 0 2u'] + meas + \
             [f'fourier {q["f"]} v(out)'] + list(q.get('extra', [])) + ['.endc', '.end']
    return '\n'.join(L) + '\n'


def run_ngspice(net, ngspice='ngspice', timeout=600):
    with tempfile.NamedTemporaryFile('w', suffix='.cir', delete=False) as f:
        f.write(net)
        path = f.name
    try:
        out = subprocess.run([ngspice, '-b', path], capture_output=True, text=True, timeout=timeout)
    finally:
        os.unlink(path)
    return out.stdout + out.stderr


def solve_bias(tubes, va, screen, vg2_b, idle_frac, p=None):
    out = run_ngspice(netlist(tubes, va, screen, vg2_b, 0.0, None, idle_frac, p))
    vals = dict((m.group(1).lower(), float(m.group(2))) for m in
                re.finditer(r'^([vi]\([\w.]+\))\s*=\s*([-+0-9.eE]+)', out, re.M))
    if len(vals) < 20:
        raise RuntimeError(out[-3000:])
    r = dict(vg1=[vals[f'v(b{n})'] for n in range(1, 5)],
             va=[vals[f'v(a{n})'] for n in range(1, 5)],
             vg2=[vals[f'v(s{n}x)'] for n in range(1, 5)],
             ia=[-vals[f'i(vsa{n})'] for n in range(1, 5)],
             ig2=[-vals[f'i(vss{n})'] for n in range(1, 5)])
    # sign: current flows from the plate node into the tube, i.e. through Vsa from + to -
    r['ia'] = [abs(x) for x in r['ia']]
    r['ig2'] = [abs(x) for x in r['ig2']]
    return r


def bias_gain(tubes, va, screen, vg2_b, bias, which, p=None):
    """Gain (V/V) from the bias source(s) in `which` to the speaker at 100 Hz, 1 kHz, 10 kHz."""
    out = run_ngspice(netlist(tubes, va, screen, vg2_b, 0.0, bias, p=p, ac=which))
    m = dict((k.lower(), float(v)) for k, v in re.findall(r'^(g\d+)\s*=\s*([-+0-9.eE]+)', out, re.M))
    if len(m) < 3:
        raise RuntimeError(out[-3000:])
    return m


def run_drive(tubes, va, screen, vg2_b, drive, bias, p=None):
    out = run_ngspice(netlist(tubes, va, screen, vg2_b, drive, bias, p=p))
    m = dict((k.lower(), float(v)) for k, v in
             re.findall(r'^(\w+)\s*=\s*([-+0-9.eE]+)', out, re.M))
    thd = re.search(r'THD:\s*([-+0-9.eE]+)\s*%', out) or \
        re.search(r'Total Harmonic Distortion:\s*([-+0-9.eE]+)', out)
    if 'vrms' not in m or not thd:
        raise RuntimeError(out[-3000:])
    q = dict(DEFAULTS, **(p or {}))
    rl = OT['rl'] * q.get('load_factor', 1.0)
    r = dict(drive=drive, pout=m['vrms'] ** 2 / rl, thd=float(thd.group(1)),
             ianode=abs(m['ianode']), ianode_pk=abs(m['ianodepk']),
             iscreen=abs(m.get('iscreen', 0.0)),
             pa=[m[f'pa{n}'] for n in range(1, 5)],
             pg2=[m[f'pg{n}'] for n in range(1, 5)],
             ig2pk=[m[f'ig2pk{n}'] for n in range(1, 5)],
             iapk=[m[f'iapk{n}'] for n in range(1, 5)],
             ov=[m[f'ov{n}'] for n in range(1, 5)],
             vgavg=[m[f'vgavg{n}'] for n in range(1, 5)],
             vgmax=[m[f'vgmax{n}'] for n in range(1, 5)], meas=m,
             raw=out if q.get('keep_raw') else None)
    return r
