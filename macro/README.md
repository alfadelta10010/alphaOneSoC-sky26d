# rf_top: the register file macro

Sylvain Munaut's ("tnt", smunaut) register file for Tiny Tapeout: 32 words of
32 bits, one write port and two read ports, a custom 12-transistor bit cell
with latches at its ports, 132.64 x 118.70 um.

## Provenance

Taken from **MichaelBell/ttsky25b-femtorv-soc @ 50aa37fdb7befa4fe2fac69f71a10d64d102df3c**
("Update register file macro", 2025-11-08), the FemtoRV SoC that ran
MicroPython at 80 MHz on this macro:

| file here | file there | sha256 |
|---|---|---|
| `rf_top.gds.gz` | `macro/rf_top.gds.gz` | `525fb010215ba3400689c0c40a4bf97415910f40498f6882d7cd027cad1d01e2` |
| `rf_top.lef` | `macro/rf_top.lef` | `b8d2dfd70500fc79bf921dba9e643da7ecb95ca1d1198f6581ab498571d11dcb` |
| `rf_top.lib` | `macro/rf_top.lib` | `4c85936bb8a29385b9953ab8797041570082bdd860f0a46a28644be7c8e8ccb8` |
| `LICENSE` | `LICENSE` (Apache-2.0) | `c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4` |

The GDS, LEF and liberty are byte-identical to the copies in the KianV
register-file edition (`ttsky26c-kianv-regfile/regfile_macro/`).

## License

The author's repositories for the macro carry no LICENSE file. `LICENSE` is
FemtoRV's copy of Apache-2.0, the terms under which these copies were
obtained.

## What the views say

- Synchronous read: `ra_addr`/`rb_addr` are captured on the rising edge of
  `clk`, and `ra_data`/`rb_data` follow about 4 ns later.
- Write-first: a read of the word written on the same edge returns the new
  data. Its timing is not characterised.
- The liberty is a placeholder, not a characterisation: setup 2.0 ns, hold
  0.2 ns, clock-to-output 4.0 ns, one nominal corner re-used for every corner.
- The LEF names the power pin `VDPWR`, the liberty `VPWR`.
