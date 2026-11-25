# Testbench

The tests use [cocotb](https://docs.cocotb.org/en/stable/) and Icarus Verilog.
They check the chip at its pins and read nothing inside the design, so the
same tests run on the RTL and on the gate-level netlist.

| File | What |
|------|------|
| `tb.v` | The chip on its board: the QSPI Pmod on `uio`, with pulled-up chip selects and floating SCK and data lines, and named wires for the UART and GPIO pins. |
| `qspi_pmod_model.v` | The QSPI Pmod: a W25Q128JV flash and two APS6404L PSRAMs. It stops the run on a command, a timing or a bus conflict the real parts would not accept. |
| `test.py` | The tests. |
| `firmware/` | The programs the chip runs in the tests, as source and as flash images. `soc.h` holds the macros of the programs that report in frames. |

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
* GPIO OUT bits 6:5 and 3:0 reach `uo_out[6:5]` and `uo_out[3:0]` (the default
  pin map), `uo_out[7]` (PWM1, idle low) stays low whatever OUT bit 7 is,
  and GPIO IN reads all of `ui_in`;
* the UART sends and receives. RTS# is not on a pin by default, so these
  tests send without flow control; `test_pinmux` tests RTS#;
* flash answers on `uio[0]`, PSRAM A on `uio[6]` and PSRAM B on `uio[7]`.

`test_stream_on` and `test_stream_off` run `firmware/tt_flash.S` with the
no-stream strap (`ui_in[2]`) low and high through the pin reset, and flip it
afterwards to show that it is read only at the pin reset. The program reports,
over the UART: the UART divisor's reset value (34); STRAPS and QSPI_CFG; the
clocks a 512-instruction straight-line block takes to run from flash, and a
checksum of a table read from flash with loads, first in SDR and then with
DDR switched on (QSPI_CFG.DDR, with DDR_CAP from `ui_in[7:5]`). The tests
check:

* QSPI_CFG.STREAM follows the strap, and the block runs faster with streaming
  on than off;
* the flash model sees no `EDh` (DDR) command before DDR is switched on and no
  `EBh` command after, and the DDR checksum equals the SDR one and the one
  computed here from the table;
* a reset with the clock running, while DDR is on, returns QSPI_CFG to SDR and
  the flash sees no `EDh` command after it.

`test_cache`, `test_gpio_irq` and `test_pinmux` run `firmware/cache.S`,
`gpio_irq.S` and `pinmux.S`. These programs report in frames on the UART
(`firmware/soc.h` lists them): a cue, on which the test acts at the pins, a
value to check, and the end, 0x5555 for a pass. After the end the test checks
that the chip powered off: every bidirectional pin released and `uo_out` at
its reset value, held for 200 clocks.

* `test_cache` writes and reads back `CACHE_CTL`; times a loop with the
  cache off and on (on is less than half); runs self-modifying code in PSRAM
  with `fence.i` after each patch, with the cache on and off; and runs 65
  words of PSRAM code cold with PBURST off and on, counting the falls of the
  PSRAM A chip select at `uio[6]`: the line bursts cut them to under half,
  and the run takes fewer clocks.
* `test_gpio_irq` makes one edge on one `ui_in` pin per cue. The program
  sees it in IN_IP and, with its IN_IE bit set, as a PLIC source 4 interrupt
  (`mip.MEIP`, claim, clear, complete), and sees no interrupt with the bit
  clear. A falling edge pends and fires when its enable is set, `wfi` wakes
  on an edge, and clearing bits that are not set changes nothing.
* `test_pinmux` reads back every pinmux code on every pin but the UART's
  TX; puts RTS# on `uo_out[5]`, pastes 64 characters from the test side as a
  sender with CTS flow control, and checks that the receive FIFO fills and
  RTS# goes high with 7 to 10 characters sent, that no character is lost
  while the program drains the FIFO, and that no overrun is flagged;
  checks the default (SD CS#) on `uo_out[5]` again; checks that a code that
  is not legal for a pin stores 0 and leaves the default map; runs PWM0 on
  `uo_out[6]` and PWM1 on `uo_out[7]` (period 65,536 clocks, 25 % high); and
  plays a tone on `uo_out[7]` (a 142,045 clock period).

## How to run

To run the RTL simulation:

```sh
make -B
```

The bench clock is 10 ns by default. `CLK_PS=19000 make -B` runs it at the
chip's 19 ns clock; every delay, period and timeout in the tests follows it.

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
