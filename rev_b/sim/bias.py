"""Per-tube bias supply on the power amp board (simulation plan, section 2; PA-2, SAFE-1).

Principle: the output rests at a clean negative reference (cold) and the DAC can only add a
current that pulls it up (hotter). Anything that removes that current gives cold bias:
DAC at zero or unpowered, op amp unpowered, +15 V or -15 V missing, the bias-enable watchdog not
toggling (control card missing, firmware stuck).

Shared, once per board:
  -80 V raw ── Rz 3.9k ── Zr ── zener string (76 V) ── GND
  Zr ── Rfz 100k ── Zf ── Cfz 10u ── GND           (filter, ~0.16 Hz)
  Dsu (signal diode) across Rfz: charges Cfz at power-on, so VNC is cold at once.
  Two P-MOSFET followers in parallel (10R source resistors): gate Zf, source = VNC (clean negative
  rail, about -73 V), drain -80 V raw. One failing open still regulates.
  Rpdn 100k from VNC to raw (discharge only: a stronger pull-down injects raw-rail ripple); Rgv 47k
  from GND to VNC (standing current).
  VNC monitor (comparator): VNC less negative than -71 V -> clamp all channels and drop BIAS_OK,
  a hardware line that inhibits the HV supplies (the -80 V rail decaying, or the reference broken).
  Watchdog: BIAS_EN (toggling 3.3 V square from the control card) ─ 100n ─ diode pump ─ Cst 1u ||
  100k ─ NMOS Qen; Qen on pulls the clamp gate low. Clamp gate is pulled up to +15 V (clamp on =
  every channel's DAC node shorted to ground = cold) unless the watchdog is running.

Per channel (x4):
  DAC (0-2.5 V) ── Rflt 10k ──┬── Cflt 330n ── GND      (DAC noise filter, 48 Hz)
                              ├── 1M ── GND             (DAC unpowered / high-Z -> cold)
                              └── clamp NMOS to GND (shared gate)
  U1 (op amp, +-15 V) + V-to-I: U1 drives NPN Q1, emitter to U1(-) and Rs 1k to GND: Ic = Vdac/Rs
  PNP mirror at +15 V (Q2 diode-connected, Q3 output, 1k emitter resistors): Q3 collector sources
  Ic into OUT.
  OUT ── Rf 30k || Cf 100n ── VNC:   OUT = VNC + Ic*Rf      (0..2.5 mA -> -73 V .. about -2 V)
  Follower NPN Q4 (300 V class): base OUT, collector GND (100R), emitter ── 22k ─┬─ 22k ── raw
                                                                      1u to GND (ripple filter);
  emitter ── Rser 1k ── BIAS ── Cb 1u ── GND ;  BIAS feeds the tube's grid leak.
"""

MODELS = """
.model QN NPN(is=1e-14 bf=200 vaf=100 cjc=4p cje=8p)
.model QHVN NPN(is=1e-14 bf=80 vaf=200 cjc=3p cje=20p)
.model QHVP PNP(is=1e-14 bf=80 vaf=150 cjc=4p cje=20p)
.model NSW NMOS(level=1 vto=1.0 kp=50m)
.model PHV VDMOS(pchan vto=-2.5 kp=0.5 rd=1 rs=0.05 cgdmax=100p cgdmin=10p cgs=300p cjo=100p is=1e-12)
.model DZ76 D(bv=76 ibv=1m rs=200 cjo=20p)
.model DSIG D(is=2.5n rs=0.5 n=1.8 cjo=4p)
.model DGRID D(is=1n rs=1 cjo=10p tt=1n)
* behavioural op amp: GBW 1 MHz, DC gain 1e5, smooth (tanh) slew and output limits 1.5 V inside
* its rails, 0 V when unpowered
.subckt OPA inp inn out vcc vee
Rn inp inx 6k
Bg 0 n2 I = {10u*tanh((V(inx)-V(inn))/10m)}
R2 n2 0 100Meg
C2 n2 0 159p
Bo o1 0 V = {(V(vcc)-V(vee)) < 3 ? 0 : (V(vcc)+V(vee))/2 + max((V(vcc)-V(vee))/2-1.5, 0.01)*tanh((V(n2)-(V(vcc)+V(vee))/2)/max((V(vcc)-V(vee))/2-1.5, 0.01))}
Ro o1 out 50
.ends OPA
"""

DEFAULTS = dict(
    raw=-80.0, vcc=15.0, vee=-15.0,
    rz=3.9e3, rfz=100e3, cfz=10e-6, rpdn=100e3, rgv=47e3, cpm=1e-6,
    rflt=10e3, cflt=330e-9, rs=1e3, re=1e3, rf=30e3, cf=100e-9,
    rpd=44e3, rser=1e3, cb=1e-6,
    en_dac=100e-9,     # DAC output noise density, V/rtHz
    en_z=10e-6,        # zener noise density, V/rtHz
    rgl=220e3,         # grid leak to the tube (load)
)


def noise_r(en):
    return en ** 2 / (4 * 1.380649e-23 * 300.15)


def netlist(p, dac='DC 1.25', raw_src=None, vcc_src=None, vee_src=None, en='toggle',
            grid_drive=None, nch=1):
    q = dict(DEFAULTS, **p)
    L = ['* bias supply', MODELS, '.options method=gear reltol=1e-3 itl4=200',
         raw_src or f'Vraw raw 0 DC {q["raw"]}',
         vcc_src or f'Vcc vcc 0 DC {q["vcc"]}',
         vee_src or f'Vee vee 0 DC {q["vee"]}']
    # clean negative reference (shared)
    L += [f'Rz zr raw {q["rz"]}', 'Dz zrn 0 DZ76',            # zener: cathode at GND, anode toward raw
          'Enz zr zrn nzz 0 1', f'Rnz nzz 0 {noise_r(q["en_z"]):.4g}',
          f'Rfz zr zf {q["rfz"]}', f'Cfz zf 0 {q["cfz"]}',
          'Dsu zf zr DSIG',            # speed-up: charges Cfz fast at power-on (VNC cold at once)
          # two P-MOSFET followers in parallel (one failing open still regulates)
          'Mvnc raw zf vs1 PHV', 'Rvs1 vs1 vnc 10', 'Mvnc2 raw zf vs2 PHV', 'Rvs2 vs2 vnc 10',
          f'Rpdn vnc raw {q["rpdn"]}', 'Cvnc vnc 0 10u',
          f'Rgv 0 vnc {q["rgv"]}']      # standing current, so the follower always conducts
    # watchdog and clamp gate (shared)
    if en == 'force':          # watchdog bypassed: bias enabled (for transfer / noise tests)
        L.append('Vforce cg 0 DC 0')
    elif en == 'toggle':
        L.append('Ven en 0 PULSE(0 3.3 0 1u 1u 0.5m 1m)')
    elif en.startswith('stop'):  # toggling, then stuck (high) from the time given: 'stop 1.0'
        ts = float(en.split()[1])
        L.append(f'Ven en0 0 PULSE(0 3.3 0 1u 1u 0.5m 1m)\nBen en 0 V = {{time < {ts} ? V(en0) : 3.3}}')
    else:
        L.append(f'Ven en 0 DC {en}')
    if en != 'force':
        L += ['Cwd en wp 100n', 'Dwd1 0 wp DSIG', 'Dwd2 wp wst DSIG', 'Cst wst 0 1u', 'Rst wst 0 100k',
              'Mqen cg wst 0 0 NSW', 'Rcg vcc cg 100k']
    # undervoltage monitor on VNC: VNC less negative than -71 V (the -80 V rail decaying, or the
    # reference broken) -> clamp every channel (cold) and drop BIAS_OK (hardware HV inhibit)
    if q.get('uvlo', True):
        L += ['Buv uvx 0 V = {V(vnc) > -71 ? 15 : 0}', 'Ruv uvx uv 1k', 'Cuv uv 0 1n',
              'Bok bias_ok 0 V = {V(uv) > 7.5 ? 0 : 1}']
    for c in range(1, nch + 1):
        L += [f'Vdac{c} d{c} 0 {dac}',
              f'Edn{c} d{c}n d{c} nd{c} 0 1', f'Rnd{c} nd{c} 0 {noise_r(q["en_dac"]):.4g}',
              f'Rflt{c} d{c}n f{c} {q["rflt"]}', f'Cflt{c} f{c} 0 {q["cflt"]}',
              f'Mcl{c} f{c} cg 0 0 NSW', f'Rfpd{c} f{c} 0 1Meg',   # DAC high-Z -> 0 V -> cold
              f'Mcu{c} f{c} uv 0 0 NSW' if q.get('uvlo', True) else '*',
              f'XU{c} f{c} e{c} u{c} vcc vee OPA',
              f'Rbq{c} u{c} bq{c} 1k',
              f'Q1_{c} c{c} bq{c} e{c} QN', f'Rs{c} e{c} 0 {q["rs"]}',
              f'Q2_{c} c{c} c{c} m2{c} QHVP', f'Re2_{c} vcc m2{c} {q["re"]}',
              f'Q3_{c} o{c} c{c} m3{c} QHVP', f'Re3_{c} vcc m3{c} {q["re"]}',
              f'Rf{c} o{c} vnc {q["rf"]}', f'Cf{c} o{c} vnc {q["cf"]}',
              f'Q4_{c} q4c{c} o{c} fe{c} QHVN', f'Rq4c{c} 0 q4c{c} 100',
              # emitter pull-down split, midpoint filtered: keeps the raw rail's ripple out
              f'Rpd{c} fe{c} pm{c} {q["rpd"] / 2}', f'Rpdb{c} pm{c} raw {q["rpd"] / 2}', f'Cpm{c} pm{c} 0 {q["cpm"]}',
              f'Rser{c} fe{c} bias{c} {q["rser"]}', f'Cb{c} bias{c} 0 {q["cb"]}',
              # load: grid leak to the coupling-cap node; grid stopper + grid diode
              f'Rgl{c} bias{c} gl{c} {q["rgl"]}', f'Ccc{c} gl{c} dr{c} 0.1u',
              f'Rst{c} gl{c} g{c} 5.6k', f'Dg{c} g{c} gk{c} DGRID', f'Rgi{c} gk{c} 0 1k']
        L.append(grid_drive.replace('{c}', str(c)) if grid_drive else f'Vdr{c} dr{c} 0 DC 0')
    return '\n'.join(L)
