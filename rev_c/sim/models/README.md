# Simulation models

**TI OPA462 PSpice model** (`opa462_ti/`, not committed). Fetch it before running
`rev_c/sim/opamp/run_sims.py`:

1. Download **SBOMAV9** ("OPA462 PSpice model", Final 1.3, 02SEP2022). It is on https://www.ti.com/product/OPA462 under Design & development → Design tools & simulation.
2. Unzip it into `rev_c/sim/models/opa462_ti/`, so that `rev_c/sim/models/opa462_ti/OPA462.LIB` exists.

It runs unmodified in ngspice-47 with `ngbehavior=ps`. `rev_c/sim/opamp/opa462_ed.lib` wraps it with the
E/D pin and the near-zero-supply current, which TI's model doesn't have (see `opamp/results.md`).
