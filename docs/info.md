<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

AlphaOneSoC is a 32-bit RISC-V system on a chip. It keeps its program and its
memory on the Tiny Tapeout QSPI Pmod, and talks to the outside through a UART
and a few GPIO pins.

**The processor** is FyraCore, an RV32IMAC core with the Zicsr, Zicntr and
Zifencei extensions. It has machine and user modes, four PMP regions, and the
standard timer and software interrupts from a CLINT.

**Memory** is the QSPI Pmod: a 16 MB flash and two 8 MB PSRAMs on one quad
bus. There is no boot ROM. Out of reset the core fetches its first instruction
from the first byte of flash and runs in place from there. SCK runs at half
the clock frequency.

| Address       | Size  | What                                              |
|---------------|-------|---------------------------------------------------|
| `0x0200_0000` | 64 KB | CLINT: `msip`, `mtimecmp`, `mtime`                |
| `0x1000_0000` | 64 KB | UART, a 16550 subset with byte-wide registers     |
| `0x1001_0000` | 64 KB | GPIO: `OUT`, `IN`, SPI `DATA`, SPI `CTRL`         |
| `0x1002_0000` | 64 KB | reserved, reads 0                                 |
| `0x2000_0000` | 16 MB | flash: read and execute                           |
| `0x8000_0000` | 16 MB | PSRAM: read, write and execute                    |

An access outside these windows raises an access fault.

**The UART** is fixed at 8N1, and its baud rate is the clock divided by 16
times the divisor. The divisor resets to 27, which is 115200 baud at a 50 MHz
clock. It has no FIFOs. A write to the transmit register waits until the
previous character has left, and RTS# tells the sender when the receiver has
room for a character.

**The GPIO block** drives six of the output pins and reads all eight input
pins. It also has an SPI transmitter (mode 3, MSB first) that takes over
`uo_out[1]` as MOSI and `uo_out[3]` as SCK when enabled, so that a display can
be written a byte per store.

**Reset.** `rst_n` is asynchronous. A low pulse of any length resets the chip,
with the clock running or stopped, and the chip leaves reset on the second
clock edge after `rst_n` rises. While it is in reset all eight bidirectional
pins are inputs, so the flash can be programmed from outside with the chip
held in reset, and the outputs hold their idle values: UART TX and RTS# high,
GPIO OUT `0x09`.

## How to test

1. Fit the QSPI Pmod on the bidirectional header and write a program to the
   start of its flash. The program must be linked to run at `0x2000_0000`.
2. Connect a terminal to the UART: `uo_out[4]` is TX, `ui_in[3]` is RX and
   `uo_out[5]` is RTS# (active low). Use CTS flow control if the terminal has
   it.
3. Hold `ui_in[0]` at the level the clock frequency needs (see below), pulse
   `rst_n` low, and release it. Keep `ui_in[0]` there until the clock has run
   for two edges after `rst_n` rose; after that it is an ordinary input.
4. The program runs. Until it sets the divisor, the UART runs at the clock
   frequency divided by 432.

`ui_in[0]` during reset picks when the chip samples data read from the Pmod:
low samples two clocks after the SCK edge that launched the data, high samples
three clocks after. Use high at clock frequencies where two clock periods are
too short for the data to make the round trip through the pads.

The tests in `test/` run a program that exercises every pin; `test/README.md`
says how to run them.

## External hardware

* [Tiny Tapeout QSPI Pmod](https://github.com/mole99/qspi-pmod) on the
  bidirectional pins (required): flash on `uio[0]`, PSRAM A on `uio[6]`, PSRAM
  B on `uio[7]`.
* A UART terminal. The Tiny Tapeout demo board's RP2350 can be one.
* Optional, on the output header: a Digilent PmodOLEDrgb (SSD1331) driven by
  the SPI transmitter, or a PmodKYPD keypad scanned through the GPIO pins.
