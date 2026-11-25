![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) ![](../../workflows/test/badge.svg) ![](../../workflows/fpga/badge.svg)

# AlphaOneSoC

A 32-bit RISC-V system on a chip for Tiny Tapeout: an RV32IMAC core that runs
from the Tiny Tapeout QSPI Pmod's flash and PSRAM, with a 256-byte instruction
cache, a PLIC, a 16550A UART, GPIO with input interrupts, an SPI controller,
a PWM timer (PWM1 plays tones on `uo_out[7]`), a gamepad receiver and a
watchdog. It is hardened for a 52.6 MHz clock.

- [Read the documentation for project](docs/info.md)
- [How the tests work, and how to run them](test/README.md)

## What is Tiny Tapeout?

Tiny Tapeout is an educational project that aims to make it easier and cheaper than ever to get your digital and analog designs manufactured on a real chip.

To learn more and get started, visit https://tinytapeout.com.

## Enable GitHub actions to build the results page

- [Enabling GitHub Pages](https://tinytapeout.com/faq/#my-github-action-is-failing-on-the-pages-part)

## Resources

- [FAQ](https://tinytapeout.com/faq/)
- [Digital design lessons](https://tinytapeout.com/digital_design/)
- [Learn how semiconductors work](https://tinytapeout.com/siliwiz/)
- [Join the community](https://tinytapeout.com/discord)
- [Build your design locally](https://www.tinytapeout.com/guides/local-hardening/)
