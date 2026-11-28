<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

AlphaOneSoC is a 32-bit RISC-V system on a chip. It keeps its program and its
memory on the Tiny Tapeout QSPI Pmod, and talks to the outside through a UART,
an SPI controller, GPIO pins, a PWM timer that also plays tones, and a
gamepad receiver.

**The processor** is FyraCore, an RV32IMAC core with the Zicsr, Zicntr and
Zifencei extensions. It has machine and user modes, four PMP regions, and the
standard timer, software and external interrupts (a CLINT and a PLIC). Its 31
general registers live in a hard macro, Sylvain Munaut's rf_top register file
(CERN-OHL-W-2.0; `macro/README.md`); the instruction cache's data memory is two
more instances of the same macro.

**The clock** is 52.6 MHz (19 ns).

**Memory** is the QSPI Pmod: a 16 MB flash and two 8 MB PSRAMs on one quad
bus. There is no boot ROM. Out of reset the core fetches its first instruction
from the first byte of flash and runs in place from there. SCK runs at half
the clock frequency. Flash reads stream by default, and double-data-rate
(DDR) flash reads can be switched on by software; see **Flash reads** below.

| Address       | Size  | What                                                          |
|---------------|-------|---------------------------------------------------------------|
| `0x0200_0000` | 64 KB | CLINT: `msip`, `mtimecmp`, `mtime`                            |
| `0x0C00_0000` | 4 MB  | PLIC: 9 sources, one context (machine mode)                   |
| `0x1000_0000` | 64 KB | UART: a 16550A with byte-wide registers                       |
| `0x1001_0000` | 64 KB | GPIO: `OUT`, `IN`, `SPICTL`, gamepad, input-change interrupt; SPI controller |
| `0x1002_0000` | 64 KB | system controller, watchdog, `PINMUX`, `CACHE_CTL`            |
| `0x1003_0000` | 64 KB | PWM timer (its registers repeat every 64 bytes through the window) |
| `0x2000_0000` | 16 MB | flash: read and execute                                       |
| `0x8000_0000` | 16 MB | PSRAM: read, write and execute                                |

An access outside these windows raises an access fault. Read the PLIC with
word loads only (a byte load of the claim register claims an interrupt).

**The UART** is a 16550A with an 8-entry receive FIFO (trigger levels 1, 2, 4
and 7 bytes), one transmit holding register, the usual interrupts and loopback,
and fixed 8N1 framing. Its baud rate is the clock divided by 16 times the
divisor. The divisor resets to 34, which is 96,749 baud at 52.6 MHz (it was
sized for 62.5 MHz): a program writes 29 (113,421 baud, -1.54 % from 115200)
before it prints. A write to the transmit register waits until the holding
register is free. Its interrupt is PLIC source 1. RTS# is not on a pin by
default (`uo_out[5]` is GPIO OUT bit 5): select it for `uo_out[5]` in
`PINMUX` for hardware flow control. RTS# is high while the receive FIFO holds
seven or more characters (fewer than two free entries) or MCR.RTS is clear, so
a sender that honours it cannot overrun the FIFO.

**The GPIO block** at `0x1001_0000` has these registers, repeated every 64
bytes through the window:

| Offset | Register                                                          |
|--------|-------------------------------------------------------------------|
| `0x00` | OUT: bit *i* drives `uo_out[i]` when `PINMUX` selects GPIO for that pin. Resets `0xB9` |
| `0x04` | IN: `ui_in[7:0]` through a two-flop synchroniser                  |
| `0x0C` | SPICTL: bit 0 EN (resets 0), bit 8 BUSY                           |
| `0x10` | GAMEPAD (read only): the last frame, see below                    |
| `0x14` | GPSTAT: bit 0 CHG (write 1 to clear), bit 1 IE                    |
| `0x18` | IN_IE: per-pin enable of the input-change interrupt (resets 0)    |
| `0x1C` | IN_IP: pending edges, one bit per `ui_in` pin; write 1 to clear   |
| `0x20` | SPI RXDATA                                                        |
| `0x24` | SPI TXDATA                                                        |
| `0x28` | SPI STATUS: bit 0 TXE, bit 1 TXR                                  |
| `0x2C` | SPI CONTROL: bit 0 CPHA, bit 1 CPOL; resets to mode 3             |
| `0x30` | SPI BAUD: SCK = clock / (2 x (BAUD + 1)); resets `0xFF`           |

**GPIO input interrupts.** Bit *i* of IN_IP sets on either edge of
`ui_in[i]` (after the synchroniser), whatever IN_IE says. The interrupt
(PLIC source 4) is high while any bit is set in both IN_IP and IN_IE, so an
edge that came while its enable was clear fires when the enable is set. To
use it: clear IN_IP, set the IN_IE bits, enable source 4 in the PLIC and
`mie.MEIE` in the core. A handler claims source 4 from the PLIC, clears the
IN_IP bits it served, and completes the claim. `wfi` wakes on an edge. Leave
IE[3] clear if a UART is on `ui_in[3]` (a start bit is an edge), and IE[6:4]
clear with a gamepad fitted (they toggle every frame).

**The SPI controller** is one SPI master. Several devices can share its bus,
each with its own chip select on a GPIO output. Its registers behave like
OpenCores tiny_spi, so Linux's `spi-oc-tiny` driver runs it, with the chip
selects on GPIO OUT. With EN set it owns `uo_out[1]` (MOSI) and `uo_out[3]`
(SCK), and samples MISO on `ui_in[1]`; both outputs come from flops. A byte
takes 16 x (BAUD + 1) clocks, all four SPI modes are supported, and a write to
TXDATA while a byte is still waiting stalls the processor until there is room.
Set EN only with every CS# high.

**The gamepad receiver** reads the Tiny Tapeout gamepad Pmod (one SNES pad):
LATCH on `ui_in[4]`, CLOCK on `ui_in[5]`, DATA on `ui_in[6]`. It keeps the
last 12 bits shifted in before LATCH (B Y SELECT START UP DOWN LEFT RIGHT A X
L R, 1 = pressed) in GAMEPAD, and an absent pad reads as no frame. GPSTAT.CHG
sets when a frame changes the value, and GPSTAT.IE enables its interrupt
(PLIC source 3).

**The pinmux.** Every `uo_out` pin has a default function (the pinout in
`info.yaml`). Two pins have one alternate function, selected by a 3-bit code in
the `PINMUX` word at `0x1002_0020`, pin *i* in bits `[4i+2:4i]`: `uo_out[5]`
code 2 is UART RTS# (code 0 is GPIO OUT bit 5), and `uo_out[6]` code 4 is
PWM0 (code 0 is GPIO OUT bit 6). `uo_out[7]` is always PWM1 and has no code. A
code that is not legal for its pin stores 0 and reads back 0, and the pin keeps
its default. The other pins are not switchable: they carry the SPI lines, the
UART's TX, and the GPIO OUT bits. All codes reset to 0. Every `uo_out` pin
comes from one flop after the mux.

**The timer/PWM** at `0x1003_0000` has the register layout of SiFive's pwm0
(Linux's `pwm-sifive` drives it): a scaled 16-bit counter and two built
comparators, whose outputs are PWM0 and PWM1 for the pinmux. PWM2 and PWM3 are
not built (`pwmcmp2/3` read `0xFFFF`). There are no PWM interrupts and no
sticky or one-shot modes (those `pwmcfg` bits read 0). The pin is high while
the scaled counter is at or above the comparator, and the counter runs only
while `enalways` is set.

**Tones** come from PWM1 on `uo_out[7]`. Set `scale` = S, `zerocmp` = 1 and
`enalways` = 1, `pwmcmp0` = N and `pwmcmp1` = N / 2: the period is
N x 2^S + 1 clocks, so the frequency is 52,631,579 / (N x 2^S + 1) Hz at
52.6 MHz (choose the smallest S with N at most 65,535). Write `pwmcount`
before enabling a tone so that the first edge is exact. To stop a tone, write
`0xFFFF` to `pwmcmp1` and `pwmcmp0`, then `pwmcfg` = 0, then `pwmcount` = 0:
`pwmcfg` = 0 alone only freezes the counter and the pin can stay high. PWM0
shares the counter and `pwmcmp0`, so while a tone plays it pulses once a
period.

**The instruction cache** is 256 bytes, direct mapped, eight lines of 32 bytes
in two 16-byte sectors (a miss fills one sector), on the fetch path only. Its
data is held in two register-file macros. It is off at reset, and switched by
`CACHE_CTL`, a word at
`0x1002_0024`:

| Bit | Meaning |
|-----|---------|
| 0 EN | 1 = fetches go through the cache (switching on starts it empty). Resets to 0, at every reset |
| 1    | reads 1: a cache is built |
| 2 PBURST | 1 = a line fill from PSRAM is one chip-select period, not four. Experimental, off at reset; needs EN and QSPI_CFG.STREAM, and a clock of at least 15 MHz (the PSRAM's tCEM; a burst is at most 101 clocks, 1.92 us at 52.6 MHz) |

A hit takes two clocks. A store, an AMO or a store-conditional that
completes invalidates the sector it hit; software must still execute `fence.i`
after writing code, which also flushes the cache. A loop that fits in the
cache runs from hits, in less than half the time it takes from flash.

**The system controller** at `0x1002_0000` reboots the chip (store `0x7777`
to `+0x00`) or powers it off until the next `rst_n` (`0x5555`). It keeps a
reset cause (`+0x04`: pin, software, watchdog; write 1 to clear), a boot-mode
byte that survives a reboot (`+0x08`), a chip ID (`+0x0C`, `0x4131_5301`),
the two straps as sampled at the last pin reset (`+0x10`, STRAPS: bit 0 is
`ui_in[0]`, bit 1 is `ui_in[2]`, the no-stream strap) and the flash-read
configuration (`+0x1C`, QSPI_CFG, below). A watchdog in the Synopsys
DesignWare layout sits at `+0x100`, so Linux's `dw_wdt` driver runs it; when
it expires it reboots the chip (PLIC source 9 pulses at the first expiry).

**PLIC sources:** 1 UART, 2 SPI, 3 gamepad change, 4 GPIO input change, 5 to
8 not built (they never pend), 9 watchdog.

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
held in reset, and the outputs hold their idle values: `uo_out` = `0x39`
(`uo_out[0]`, SCK, UART TX and `uo_out[5]` high, the rest low), and GPIO OUT
`0xB9`. `uo_out[0]` and `uo_out[5]` are therefore the natural choice for
active-low chip selects.
A reboot from the system controller or the watchdog looks the same at the
pins.

## How to test

1. Fit the QSPI Pmod on the bidirectional header and write a program to the
   start of its flash. The program must be linked to run at `0x2000_0000`.
2. Connect a terminal to the UART: `uo_out[4]` is TX and `ui_in[3]` is RX.
   For flow control, write `0x0020_0000` to `PINMUX` (code 2, RTS#, on
   `uo_out[5]`) and use CTS on the terminal side.
3. Hold `ui_in[0]` at the level the clock frequency needs (see below), and
   `ui_in[2]` low (streaming on; high for streaming off), pulse `rst_n` low,
   and release it. Keep both there until the clock has run for two edges
   after `rst_n` rose; after that they are ordinary inputs, and a reboot
   does not read them again.
4. The program runs. Until it sets the divisor, the UART runs at the clock
   frequency divided by 544.
5. Try the newer blocks: write `1` to `CACHE_CTL` and time a loop with
   `mcycle`; set a bit of IN_IE and toggle that `ui_in` pin to see the
   interrupt (poll `mip.MEIP` with `mstatus.MIE` clear, or take the trap);
   write `0x0020_0000` to `PINMUX` for RTS# on `uo_out[5]`; play a tone on
   `uo_out[7]` with the PWM.

`ui_in[0]` during reset picks when the chip samples data read from the Pmod:
low samples two clocks after the SCK edge that launched the data, high samples
three clocks after. Use high at clock frequencies where two clock periods are
too short for the data to make the round trip through the pads: low at
52.6 MHz, the chip's clock (round trips up to about 32 ns; high is the
fallback), high at 60 MHz and above.

The tests in `test/` run programs that exercise every pin, the flash read
modes, the instruction cache, the GPIO input interrupt and the pinmux;
`test/README.md` says how to run them.

## External hardware

* [Tiny Tapeout QSPI Pmod](https://github.com/mole99/qspi-pmod) on the
  bidirectional pins (required): flash on `uio[0]`, PSRAM A on `uio[6]`, PSRAM
  B on `uio[7]`.
* A UART terminal. The Tiny Tapeout demo board's RP2350 can be one.
Everything else is optional; the chip does not assume any of it.

* **SPI devices**: anything with an SPI interface, for example a display
  (SSD1331 OLED, ILI9341 TFT), an SD card in SPI mode, or a W5500 Ethernet
  controller. The bus is MOSI `uo_out[1]`, SCK `uo_out[3]` and MISO
  `ui_in[1]`. Each device's chip select, and any control line it needs (a
  display's data/command or reset), goes on a free GPIO output; `uo_out[0]`
  and `uo_out[5]` idle high. A device's interrupt output can go on a free
  `ui_in` pin with the GPIO input-change interrupt. For a device that drives
  MISO, the input on `ui_in[1]` must not be pulled or driven by anything else
  (on the Tiny Tapeout demo board, its DIP switch off). An SD card must see at
  least 74 clocks with every CS# high, then CMD0, before any other device on
  the bus is addressed.
* **Tones**: a speaker or the Tiny Tapeout Audio Pmod on `uo_out[7]` (PWM1).
* **Gamepad**: the Tiny Tapeout gamepad Pmod on `ui_in[4..6]`.
* **GPIO**: any `ui_in` pin not used above is a GPIO input, and any
  `uo_out[0..3,5,6]` pin not used above is a GPIO output.
