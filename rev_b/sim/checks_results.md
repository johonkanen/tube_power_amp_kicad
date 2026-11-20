## -80 V rail current, 4 channels (all at the same DAC code)

| Vdac (V) | bias (V) | -80 V (mA) | +15 V (mA) | -15 V (mA) |
|---|---|---|---|---|
| 0.00 | -74.35 | 3.05 | 0.00 | 0.00 |
| 0.50 | -59.52 | 6.36 | 3.95 | 0.00 |
| 1.00 | -45.13 | 9.58 | 7.85 | 0.00 |
| 1.36 | -34.89 | 11.89 | 10.65 | 0.00 |
| 1.60 | -28.04 | 13.42 | 12.52 | 0.00 |
| 2.00 | -16.65 | 15.97 | 15.62 | 0.00 |
| 2.41 | -5.04 | 18.57 | 18.80 | 0.00 |
| 2.50 | -2.51 | 19.14 | 19.50 | 0.00 |

## Cathode-current filter

| Cb1 to | trip after a step to 400 mA (ms) | ripple, class AB pulses (mA pp) | reading (mA, true 161.4) | settling to 0.5 mA (ms) | max after the step (V) |
|---|---|---|---|---|---|
| floating (as simulated in the master) | 23.0 | 1.23 | 160.5 | 400 | 4.00 |
| fb (unity-gain Sallen-Key; not drawn) | 28.1 | 4.21 | 160.5 | 400 | 4.00 |

## Grid current, 150 V peak overdrive for 0.2 s

| grid leak / coupling cap | bias (V) | bias node moves (V) | most negative grid-leak foot vs bias (V, blocking) |
|---|---|---|---|
| 220k / 0.1u (master sim) | -38.1 | 0.14 | -239 |
| 100k / 47n (drawn) | -38.1 | 0.26 | -226 |

## VNC spread (DAC at zero)

| zener string (V) | follower Vgs(th) (V) | VNC (V) |
|---|---|---|
| 74.5 | -1.0 | -73.78 |
| 74.5 | -2.5 | -72.28 |
| 74.5 | -4.0 | -70.78 |
| 76.0 | -1.0 | -75.22 |
| 76.0 | -2.5 | -73.72 |
| 76.0 | -4.0 | -72.22 |
| 77.5 | -1.0 | -76.65 |
| 77.5 | -2.5 | -75.15 |
| 77.5 | -4.0 | -73.65 |

## VNC monitor threshold: -80 V source lost at 1.5 s, +-15 V up, DAC 2.0 V, BIAS_EN 5 V 10 kHz from 0.5 s

| threshold (V) | bias before (V) | VNC before (V) | commanded bias reached after BIAS_EN starts (ms) | BIAS_OK low after loss (ms) | hottest bias after loss (V) |
|---|---|---|---|---|---|
| -71 | -16.7 | -73.56 | 17 | 185 | -14.2 |
| -68.4 | -16.7 | -73.56 | 17 | 247 | -11.6 |
