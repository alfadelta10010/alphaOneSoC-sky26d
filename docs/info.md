<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

AlphaOneSoC is a 32-bit RISC-V system on a chip. It keeps its program and its
memory on the Tiny Tapeout QSPI Pmod, and talks to the outside through a UART,
an SPI controller and a few GPIO pins.

**The processor** is FyraCore, an RV32IMAC core with the Zicsr, Zicntr and
Zifencei extensions. It has machine and user modes, four PMP regions, and the
standard timer and software interrupts from a CLINT. Its 31 general registers
live in a hard macro, Sylvain Munaut's rf_top register file (CERN-OHL-W-2.0;
`macro/README.md`).

**The clock** is 62.5 MHz (16 ns): the design meets timing at that frequency
at every corner, the slow one (100 C, 1.60 V) included. The board may also
run it at 60 MHz.

**Memory** is the QSPI Pmod: a 16 MB flash and two 8 MB PSRAMs on one quad
bus. There is no boot ROM. Out of reset the core fetches its first instruction
from the first byte of flash and runs in place from there. SCK runs at half
the clock frequency. Flash reads stream by default, and double-data-rate
(DDR) flash reads can be switched on by software; see **Flash reads** below.

| Address       | Size  | What                                              |
|---------------|-------|---------------------------------------------------|
| `0x0200_0000` | 64 KB | CLINT: `msip`, `mtimecmp`, `mtime`                |
| `0x1000_0000` | 64 KB | UART, a 16550 subset with byte-wide registers     |
| `0x1001_0000` | 64 KB | GPIO: `OUT`, `IN`, `SPICTL`; SPI controller       |
| `0x1002_0000` | 64 KB | system controller and watchdog                    |
| `0x2000_0000` | 16 MB | flash: read and execute                           |
| `0x8000_0000` | 16 MB | PSRAM: read, write and execute                    |

An access outside these windows raises an access fault.

**The UART** is fixed at 8N1, and its baud rate is the clock divided by 16
times the divisor. The divisor resets to 34, which is 114,890 baud (-0.27 %
from 115200) at 62.5 MHz; at 60 MHz set it to 33 (113,636 baud, -1.4 %). It
has no FIFOs. A write to the transmit register waits until the previous character
has left, and RTS# tells the sender when the receiver has room for a
character.

**The GPIO block** drives six of the output pins and reads all eight input
pins, through a two-flop synchroniser. OUT bit 7 is the SD card's CS#.

| Offset | Register                                                          |
|--------|-------------------------------------------------------------------|
| `0x00` | OUT: bit *i* drives `uo_out[i]`; bits 4 and 5 read 0. Resets `0x89` |
| `0x04` | IN: `ui_in[7:0]`                                                  |
| `0x0C` | SPICTL: bit 0 EN (resets 0), bit 8 BUSY                           |
| `0x20` | SPI RXDATA                                                        |
| `0x24` | SPI TXDATA                                                        |
| `0x28` | SPI STATUS: bit 0 TXE, bit 1 TXR                                  |
| `0x2C` | SPI CONTROL: bit 0 CPHA, bit 1 CPOL; resets to mode 3             |
| `0x30` | SPI BAUD: SCK = clock / (2 x (BAUD + 1)); resets `0xFF`           |

The registers repeat every 64 bytes through the window.

**The SPI controller** is a master for an SD card and a display on one bus.
Its registers behave like OpenCores tiny_spi, so Linux's `spi-oc-tiny` driver
runs it, with the chip selects on GPIO OUT. With EN set it owns `uo_out[1]`
(MOSI) and `uo_out[3]` (SCK), and samples MISO on `ui_in[1]`; both outputs
come from flops. A byte takes 16 x (BAUD + 1) clocks, all four SPI modes
are supported, and a write to TXDATA while a byte is still waiting stalls
the processor until there is room. Set EN only with every CS# high.

**The system controller** at `0x1002_0000` reboots the chip (store `0x7777`
to `+0x00`) or powers it off until the next `rst_n` (`0x5555`). It keeps a
reset cause (`+0x04`: pin, software, watchdog; write 1 to clear), a boot-mode
byte that survives a reboot (`+0x08`), a chip ID (`+0x0C`, `0x4131_5301`),
the two straps as sampled at the last pin reset (`+0x10`, STRAPS: bit 0 is
`ui_in[0]`, bit 1 is `ui_in[2]`, the no-stream strap) and the flash-read
configuration (`+0x1C`, QSPI_CFG, below). A watchdog in the Synopsys
DesignWare layout sits at `+0x100`, so Linux's `dw_wdt` driver runs it; when
it expires it reboots the chip.

**Flash reads.** The flash is read with the quad I/O read (`EBh`, command on
IO0, address and data on all four lines). Two things change how, both set in
QSPI_CFG at `0x1002_001C` (word, byte lane 0):

| Bits  | Field   | Meaning                                                              | Resets to               |
|-------|---------|----------------------------------------------------------------------|-------------------------|
| [0]   | STREAM  | a read that continues where the last one ended keeps chip select low and sends only the data clocks | 1, or 0 if `ui_in[2]` was high at the pin reset |
| [1]   | DDR     | every flash read is a double-data-rate read (`EDh`, both SCK edges)   | 0                       |
| [4:2] | DDR_CAP | the half-clock point at which a DDR nibble is captured, 0 to 7       | 2                       |

* **Streaming** is on by default: instruction fetch runs straight through
  flash at 8 SCK clocks per 4 bytes, instead of a new command and address
  (about 28 SCK) for every fetch. A jump, a data access or any other request
  closes the stream first (chip select high for two clocks). Streaming is
  flash only; PSRAM accesses are unchanged. Hold `ui_in[2]` high through the
  pin reset to start with streaming off (STREAM = 0), for instance to
  separate a streaming problem from other faults. Software can also clear
  STREAM; no fence or jump is needed after writing QSPI_CFG, and a read in
  flight finishes in the mode it started in.
* **DDR flash reads** are off at reset. Every reset (pin, system-controller
  reboot, watchdog expiry) clears QSPI_CFG to SDR, `DDR_CAP` 2, so a reboot
  always comes back in the mode every flash accepts. DDR needs the
  Winbond W25Q128JV-**DTR** flash (the `-IM` part has no DTR read) with its
  Quad Enable bit set. The flash launches a nibble on every SCK edge, and
  the time it takes to reach the chip (pads, board, Pmod) is not known in
  advance, so software chooses `DDR_CAP`. The routine to follow: run from
  PSRAM (a fetch from flash closes the stream and would run in the mode
  under test); copy a block of flash into PSRAM with DDR off; for each
  `DDR_CAP` from 1 to 6 switch DDR on, read the block back with loads a few
  times, compare, and switch DDR off again; take the middle of the longest
  run of passing points (the later one when two are equally good, because
  the die warms and delays grow); if none passes, stay in SDR. A load
  sweep never exercises a stream continuation, so then run a straight-line
  block of flash code in DDR with the watchdog armed and a note in
  BOOT_MODE: a hang ends in a watchdog reboot, which comes back in SDR, and
  the note tells the next boot not to try again. Once the watchdog is armed
  it cannot be disabled and the program must service it.
* **Handing the Pmod over.** A board master that has programmed or used the
  flash before releasing the Pmod must leave the flash idle (no program,
  erase or status write running, nothing suspended), not in deep power-down,
  without a burst wrap (the power-up default) and with Quad Enable set. The
  chip's start-up sequence undoes quad, dual and DTR continuous-read mode
  and QPI mode and nothing else; a flash left in any other state gives a boot
  failure with no diagnosis, or silently wrong fetches for a wrap.

**Reset.** `rst_n` is asynchronous. A low pulse of any length resets the chip,
with the clock running or stopped, and the chip leaves reset on the second
clock edge after `rst_n` rises. While it is in reset all eight bidirectional
pins are inputs, so the flash can be programmed from outside with the chip
held in reset, and the outputs hold their idle values: UART TX and RTS# high,
GPIO OUT `0x89` (`uo_out` = `0xB9`). A reboot from the system controller
or the watchdog looks the same at the pins.

## How to test

1. Fit the QSPI Pmod on the bidirectional header and write a program to the
   start of its flash. The program must be linked to run at `0x2000_0000`.
2. Connect a terminal to the UART: `uo_out[4]` is TX, `ui_in[3]` is RX and
   `uo_out[5]` is RTS# (active low). Use CTS flow control if the terminal has
   it.
3. Hold `ui_in[0]` at the level the clock frequency needs (see below), and
   `ui_in[2]` low (streaming on; high for streaming off), pulse `rst_n` low,
   and release it. Keep both there until the clock has run for two edges
   after `rst_n` rose; after that they are ordinary inputs, and a reboot
   does not read them again.
4. The program runs. Until it sets the divisor, the UART runs at the clock
   frequency divided by 432.

`ui_in[0]` during reset picks when the chip samples data read from the Pmod:
low samples two clocks after the SCK edge that launched the data, high samples
three clocks after. Use high at clock frequencies where two clock periods are
too short for the data to make the round trip through the pads: high at
62.5 MHz and 60 MHz, low at 50 MHz and below.

The tests in `test/` run a program that exercises every pin; `test/README.md`
says how to run them.

## External hardware

* [Tiny Tapeout QSPI Pmod](https://github.com/mole99/qspi-pmod) on the
  bidirectional pins (required): flash on `uio[0]`, PSRAM A on `uio[6]`, PSRAM
  B on `uio[7]`.
* A UART terminal. The Tiny Tapeout demo board's RP2350 can be one.
* Optional, on the output header: a Digilent PmodOLEDrgb (SSD1331) driven by
  the SPI controller, or a PmodKYPD keypad scanned through the GPIO pins.
* Optional: an SD card (for example a Digilent PmodMicroSD) on the same SPI
  bus: MOSI `uo_out[1]`, SCK `uo_out[3]`, MISO `ui_in[1]` and CS#
  `uo_out[7]`. With the card fitted, DIP switch 2 must be off. On every boot,
  before any other SPI traffic, clock at least 74 cycles with every CS# high
  and then send CMD0 to the card, so that it is in SPI mode before the
  display is written.
