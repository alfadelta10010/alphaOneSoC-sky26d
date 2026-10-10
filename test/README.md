# Testbench

The tests use [cocotb](https://docs.cocotb.org/en/stable/) and Icarus Verilog.
They check the chip at its pins and read nothing inside the design, so the
same tests run on the RTL and on the gate-level netlist.

| File | What |
|------|------|
| `tb.v` | The chip on its board: the QSPI Pmod on `uio`, with pulled-up chip selects and floating SCK and data lines, and named wires for the UART and GPIO pins. |
| `qspi_pmod_model.v` | The QSPI Pmod: a W25Q128JV flash and two APS6404L PSRAMs. It stops the run on a command, a timing or a bus conflict the real parts would not accept. |
| `test.py` | The tests. |
| `firmware/` | The programs the chip runs in the tests, as source and as flash images. |

## Tests

`test_pins`, `test_pins_slow_devices` and `test_pins_rd_late` run
`firmware/tt_pins.S` with three settings of the Pmod's read timing, the last
with the `ui_in[0]` strap high. The program is reset three times on the way
and has to start again each time: with the clock stopped and started only
after the pulse, as the demo board's firmware does it; in the middle of a
flash read with the clock running; and by a pulse shorter than a clock. Each
test checks:

* in reset, from `rst_n` falling to the second clock edge after it rises,
  every bidirectional pin is an input and `uo_out` holds its reset value,
  with or without a clock; the chip drives SCK and the chip selects on the
  third edge, no sooner and no later;
* no output is X from the first reset on;
* the `ui_in[0]` strap may change right after that second edge;
* GPIO OUT reaches `uo_out[7:6]` and `uo_out[3:0]`, and GPIO IN reads all of
  `ui_in`;
* the UART sends and receives, and RTS# is high while a received byte waits;
* flash answers on `uio[0]`, PSRAM A on `uio[6]` and PSRAM B on `uio[7]`.

## How to run

To run the RTL simulation:

```sh
make -B
```

To run the gate-level simulation, first harden the project, and copy
`../runs/wokwi/final/pnl/tt_um_alfadelta10010_alphaone_soc.pnl.v` to
`gate_level_netlist.v`. Then, with `PDK_ROOT` pointing at the PDK the harden
used, run:

```sh
make -B GATES=yes
```

The GitHub `gds` workflow does this on every push, in its `gl_test` job.

If you wish to save the waveform in VCD format instead of FST format, edit tb.v to use `$dumpfile("tb.vcd");` and then run:

```sh
make -B FST=
```

This will generate `tb.vcd` instead of `tb.fst`.

## Changing a test program

The flash images in `firmware/*.hex` are checked in, so the tests need no
RISC-V toolchain. After editing a `.S`, rebuild its image and commit both:

```sh
make -C firmware
```

This needs `riscv64-unknown-elf-gcc` (set `TOOLCHAIN` for another prefix).

## How to view the waveform file

Using GTKWave

```sh
gtkwave tb.fst tb.gtkw
```

Using Surfer

```sh
surfer tb.fst
```
