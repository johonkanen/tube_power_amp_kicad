"""Cathode-current sense chain (PA-4, SAFE-2): the filter variants, shared by run_bias_supply.py
and run_sense_filter.py.

Chain: 1 ohm shunt with a power diode across it, 10k / 10 nF, the filter, gain 10 (9k / 1k),
1k / 100 nF to the ADC and the over-current comparator (2.20 V = 220 mA).

RECOMMENDED is the filter of the design. 'one_pole' is what the 2026-11-20 netlist really
simulated: it had `Cb1 a2 b1 330n` with node b1 connected to nothing (a floating capacitor), so
the "2nd-order 3.3 Hz Sallen-Key" of the documents was one real pole at 4.6 Hz.
"""
import bias

RECOMMENDED = 'two_real_220'
AS_SIMULATED = 'one_pole'
THRESH = 2.2          # V at the comparator = 220 mA
GAIN = 'Rg1 y fb 9k\nRg2 fb 0 1k\nRout y adc 1k\nCadc adc 0 100n'
FRONT = 'Rin k a1 10k\nCcl a1 0 10n'

# name: (description, op amps per tube, netlist body between the nodes k (shunt) and adc)
VARIANTS = {
    'one_pole': ('As simulated 2026-11-20 and as drawn (power amp rev B): 10k + 47k + 47k into 330 nF, one real pole; Cb1 not fitted', 1,
                 f'{FRONT}\nRa a1 a2 47k\nRb a2 a3 47k\nCb2 a3 0 330n\nXU a3 fb y vcc vee OPA\n{GAIN}'),
    'two_real_330': ('Two real poles: 47k / 330 nF to ground, twice (the same parts, Cb1 to ground)', 1,
                 f'{FRONT}\nRa a1 a2 47k\nCb1 a2 0 330n\nRb a2 a3 47k\nCb2 a3 0 330n\nXU a3 fb y vcc vee OPA\n{GAIN}'),
    'two_real_220': ('Two real poles: 47k / 220 nF to ground, twice (recommended 2026-11-22)', 1,
                      f'{FRONT}\nRa a1 a2 47k\nCb1 a2 0 220n\nRb a2 a3 47k\nCb2 a3 0 220n\nXU a3 fb y vcc vee OPA\n{GAIN}'),
    'sk_3hz3': ('The documented filter: 2nd-order 3.3 Hz Sallen-Key (Butterworth; 100k, 100k, 680 nF, 330 nF around a unity-gain buffer), then the gain of 10', 2,
                f'{FRONT}\nRa a1 a2 100k\nCb1 a2 b 680n\nRb a2 a3 100k\nCb2 a3 0 330n\nXB a3 b b vcc vee OPA\nXU b fb y vcc vee OPA\n{GAIN}'),
    'sk_10hz': ('2nd-order 10 Hz Sallen-Key (Butterworth; 47k, 47k, 470 nF, 220 nF around a unity-gain buffer), then the gain of 10', 2,
                f'{FRONT}\nRa a1 a2 47k\nCb1 a2 b 470n\nRb a2 a3 47k\nCb2 a3 0 220n\nXB a3 b b vcc vee OPA\nXU b fb y vcc vee OPA\n{GAIN}'),
    'sk_fb': ('One op amp, Cb1 returned to the gain stage\'s inverting input (47k, 47k, 330 nF, 330 nF): the power amp session\'s check', 1,
              f'{FRONT}\nRa a1 a2 47k\nCb1 a2 fb 330n\nRb a2 a3 47k\nCb2 a3 0 330n\nXU a3 fb y vcc vee OPA\n{GAIN}'),
}
ORDER = list(VARIANTS)
SHORT = {'one_pole': 'one pole 4.6 Hz (as simulated, as drawn)', 'two_real_330': 'two real poles 3.5 / 27 Hz',
         'two_real_220': 'two real poles 5.3 / 40 Hz (recommended)', 'sk_3hz3': 'Sallen-Key 3.3 Hz (documented)',
         'sk_10hz': 'Sallen-Key 10 Hz', 'sk_fb': 'Cb1 to the inverting input'}


def subckts():
    return '\n'.join(f'.subckt SENSE_{n} k adc vcc vee\n{body}\n.ends' for n, (_, _, body) in VARIANTS.items())


def chains(knode, tag):
    """One instance of every variant on the cathode node knode; outputs adc_<tag>_<variant>."""
    return '\n'.join(f'XS{tag}{n} {knode} adc_{tag}_{n} fvcc fvee SENSE_{n}' for n in ORDER)


COMMON = bias.MODELS + '\nVfcc fvcc 0 15\nVfee fvee 0 -15\n.model DPWR D(is=1e-9 rs=0.01 n=1.5)\n'


