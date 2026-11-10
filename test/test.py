# SPDX-License-Identifier: Apache-2.0
"""Pin-level tests of the chip.

Every check here is made at the chip's 24 pins (plus clk and rst_n), through
the board in tb.v, and reads nothing inside the design. So the same tests run
on the RTL (`make`) and on the gate-level netlist (`make GATES=yes`).

The chip boots from the QSPI Pmod model's flash. Each test loads its program
there (firmware/*.hex) and holds the chip in reset while it does.
"""

import os
import re

import cocotb
from cocotb.queue import Queue
from cocotb.triggers import ClockCycles, FallingEdge, RisingEdge, Timer

CLK_NS = 10
# firmware/tt_pins.S sets the UART divisor to 1: 16 clocks a bit
BIT_NS = 16 * CLK_NS

FIRMWARE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "firmware")

# out_vals in firmware/tt_pins.S, and the ui_in patterns it is shown
OUT_VALS = [0x01, 0x02, 0x04, 0x08, 0x40, 0x80, 0xFF, 0x00, 0x09]
IN_PATS = [0x01, 0x02, 0x04, 0x10, 0x20, 0x40, 0x80, 0x00, 0xF7]

# uo_out while the chip is in reset: TX and RTS# high, GPIO OUT 0x89
UO_RESET = "10111001"


def bits(signal):
    """A signal's value as a string of 0, 1, x and z."""
    return str(signal.value).lower()


def read_hex(name):
    """A flash image as {address: byte} (objcopy -O verilog)."""
    image = {}
    addr = 0
    with open(os.path.join(FIRMWARE, name)) as f:
        for token in f.read().split():
            if token.startswith("@"):
                addr = int(token[1:], 16)
            else:
                image[addr] = int(token, 16)
                addr += 1
    return image


class Board:
    """The chip's pins, watched on every clock, and the board's clock, reset
    and UART on them."""

    def __init__(self, dut):
        self.dut = dut
        self.rx = Queue()  # bytes the chip sent
        self.clock_on = False  # the board's clock is running
        self.reset_seen = False
        # The chip is in reset from rst_n falling to the second clock edge
        # after it rises. `edges` counts the clock edges since then, up to 3.
        self.edges = 3
        self.cs_falls = [0, 0, 0]  # flash, PSRAM A, PSRAM B
        self.sck_rises = 0
        self.loaded = set()

    def load_flash(self, name):
        """Put a program in the Pmod's flash, in place of the last one."""
        flash = self.dut.pmod.flash
        image = read_hex(name)
        for addr in self.loaded - set(image):
            flash[addr].value = 0
        for addr, byte in image.items():
            flash[addr].value = byte
        self.loaded = set(image)

    def start(self):
        dut = self.dut
        cocotb.start_soon(self._clock())
        cocotb.start_soon(self._count_edges())
        cocotb.start_soon(self._watch_pins())
        cocotb.start_soon(self._count_falls(dut.qspi_cs0_n, 0))
        cocotb.start_soon(self._count_falls(dut.qspi_cs1_n, 1))
        cocotb.start_soon(self._count_falls(dut.qspi_cs2_n, 2))
        cocotb.start_soon(self._count_sck())
        cocotb.start_soon(self._uart_receive())

    async def _clock(self):
        """The board's clock, which it can stop."""
        level = 0
        self.dut.clk.value = 0
        while True:
            await Timer(CLK_NS // 2, unit="ns")
            if self.clock_on:
                level = 1 - level
                self.dut.clk.value = level

    def reset(self, asserted):
        """Drive rst_n."""
        self.dut.rst_n.value = 0 if asserted else 1
        if asserted:
            self.edges = 0
            self.reset_seen = True

    async def _count_edges(self):
        dut = self.dut
        while True:
            await RisingEdge(dut.clk)
            if bits(dut.rst_n) == "1" and self.edges < 3:
                self.edges += 1

    def in_reset(self):
        return bits(self.dut.rst_n) != "1" or self.edges < 2

    def check_reset_pins(self, when):
        """All of uio released, and uo_out at its reset value."""
        dut = self.dut
        assert bits(dut.uio_oe) == "00000000", f"uio_oe = {bits(dut.uio_oe)} {when}"
        assert bits(dut.uo_out) == UO_RESET, (
            f"uo_out = {bits(dut.uo_out)} {when}, want {UO_RESET}"
        )

    async def _watch_pins(self):
        dut = self.dut
        edges_q = 3  # `edges` at the previous falling edge
        while True:
            await FallingEdge(dut.clk)
            if not self.reset_seen:
                continue
            # uio_oe is uio[7:0], so oe[7 - n] is pin n
            oe = bits(dut.uio_oe)
            assert "x" not in oe and "z" not in oe, f"uio_oe = {oe}"
            assert oe[7] == oe[4] == oe[1] == oe[0], (
                f"uio_oe = {oe}: the SCK and chip select enables differ"
            )
            assert oe[6] == oe[5] == oe[3] == oe[2], (
                f"uio_oe = {oe}: the SD0..SD3 enables differ"
            )
            uo = bits(dut.uo_out)
            assert "x" not in uo and "z" not in uo, f"uo_out = {uo}"
            out = bits(dut.uio_out)
            for n in range(8):
                assert not (oe[7 - n] == "1" and out[7 - n] in "xz"), (
                    f"uio_out[{n}] is driven with an X"
                )
            if self.in_reset():
                self.check_reset_pins("in reset")
            # The two edges after rst_n rises are the SoC's reset. On the
            # third it drives SCK and the chip selects, so a release one edge
            # shorter or longer shows here.
            elif self.edges == 2:
                self.check_reset_pins("after the second clock edge out of reset")
            elif self.edges == 3 and edges_q == 2:
                assert oe[4] == "1", (
                    "SCK and the chip selects not driven on the third clock edge out of reset"
                )
            edges_q = self.edges

    async def _count_falls(self, signal, which):
        while True:
            await FallingEdge(signal)
            self.cs_falls[which] += 1

    async def _count_sck(self):
        while True:
            await RisingEdge(self.dut.qspi_sck)
            self.sck_rises += 1

    async def _uart_receive(self):
        """Decode uart_tx: 8N1, each bit sampled at its middle."""
        tx = self.dut.uart_tx
        while True:
            await FallingEdge(tx)
            await Timer(BIT_NS // 2, unit="ns")
            assert bits(tx) == "0", "UART TX: start bit not low at its middle"
            byte = 0
            for n in range(8):
                await Timer(BIT_NS, unit="ns")
                bit = bits(tx)
                assert bit in "01", "UART TX: X in a data bit"
                byte |= int(bit) << n
            await Timer(BIT_NS, unit="ns")
            assert bits(tx) == "1", f"UART TX: framing error after byte {byte:#04x}"
            self.dut._log.debug(f"UART byte {byte:#04x}")
            self.rx.put_nowait(byte)

    async def aim_at_flash_read(self):
        """Wait for the flash to be driving read data, two clocks into it."""
        dut = self.dut
        while True:
            await RisingEdge(dut.pmod_oe)
            if bits(dut.qspi_cs0_n) == "0":
                break
        await ClockCycles(dut.clk, 2)
        assert bits(dut.pmod_oe) == "1" and bits(dut.qspi_cs0_n) == "0", (
            "the reset was not aimed at a flash read"
        )

    async def uart_send(self, byte):
        """Send a byte to uart_rx as the demo board's RP2350 does, waiting
        for CTS (the chip's RTS#) first."""
        dut = self.dut
        while bits(dut.uart_rts_n) != "0":
            await RisingEdge(dut.clk)
        await Timer(3, unit="ns")
        for bit in [0] + [(byte >> n) & 1 for n in range(8)] + [1]:
            dut.uart_rx.value = bit
            await Timer(BIT_NS, unit="ns")
        # The program cannot have read the byte in the half bit since its
        # stop bit was sampled, so the chip must not be asking for another.
        assert bits(dut.uart_rts_n) == "1", (
            "RTS# low at the end of a received byte, before the program read it"
        )

    def ram_word(self, addr):
        """A little-endian word of the Pmod's PSRAM (A at 0, B at 8 MB)."""
        ram = self.dut.pmod.ram
        return sum(int(ram[addr + n].value) << (8 * n) for n in range(4))


async def pins(dut, rd_late, delay_ns, hold_ns):
    """firmware/tt_pins.S: every pin, through three resets, with the QSPI
    devices answering delay_ns after SCK falls and holding the old data for
    hold_ns."""
    board = Board(dut)

    # The Pmod's timing, and the program.
    dut.pmod.delay_ns.value = delay_ns
    dut.pmod.hold_ns.value = hold_ns
    board.load_flash("tt_pins.hex")

    dut.ena.value = 1
    dut.rst_n.value = 1
    dut.uart_rx.value = 1
    dut.gpio_in.value = rd_late  # ui_in[0], the qspi_rd_late strap
    board.start()

    # Reset 1, as the demo board's firmware does it: the clock stopped, a
    # pulse on rst_n, then the clock. The chip stays in reset, pins and all,
    # until the clock has run for two edges.
    await Timer(20, unit="ns")
    board.reset(True)
    await Timer(2, unit="ns")
    board.check_reset_pins("2 ns after rst_n fell, the clock stopped")
    await Timer(48, unit="ns")
    board.reset(False)
    await Timer(30, unit="ns")
    board.check_reset_pins("after a reset pulse with the clock stopped")
    board.clock_on = True

    # Reset 2: the clock running, off the clock edge, in the middle of a flash
    # read, while the flash is driving the bus.
    await board.aim_at_flash_read()
    await Timer(3, unit="ns")
    board.reset(True)
    await Timer(2, unit="ns")
    board.check_reset_pins("2 ns after rst_n fell in a flash read")
    await ClockCycles(dut.clk, 6)
    await Timer(1, unit="ns")
    board.reset(False)

    # Reset 3: the same, but a pulse that fits between two clock edges.
    await board.aim_at_flash_read()
    await Timer(1, unit="ns")
    board.reset(True)
    await Timer(2, unit="ns")
    board.check_reset_pins("2 ns after rst_n fell, a short pulse")
    await Timer(1, unit="ns")
    board.reset(False)
    assert board.rx.empty(), "UART traffic before the last reset"
    board.cs_falls = [0, 0, 0]
    board.sck_rises = 0

    # The strap is free to change once the second edge has gone.
    await ClockCycles(dut.clk, 2)
    await Timer(1, unit="ns")
    dut.gpio_in.value = 1 - rd_late

    # 1. GPIO OUT: an 'o' after each value written
    for value in OUT_VALS:
        byte = await board.rx.get()
        assert byte == ord("o"), f"got {byte:#04x}, want 'o'"
        want = f"{value >> 6:02b}{value & 0xF:04b}"
        assert bits(dut.gpio_out) == want, (
            f"OUT = {value:#04x}: uo_out[7:6], [3:0] = {bits(dut.gpio_out)}, want {want}"
        )

    # 2. GPIO IN and UART RX: after each 'i', a pattern on ui_in and a byte;
    #    the program sends back the byte, then IN
    for k, pattern in enumerate(IN_PATS):
        byte = await board.rx.get()
        assert byte == ord("i"), f"got {byte:#04x}, want 'i'"
        dut.gpio_in.value = pattern
        await board.uart_send(0x30 + k)
        byte = await board.rx.get()
        assert byte == 0x30 + k, f"RX: sent {0x30 + k:#04x}, the program read {byte:#04x}"
        byte = await board.rx.get()
        want = pattern | 0x08  # ui_in[3] is the RX line, idle (high) by now
        assert byte == want, f"ui_in = {want:08b}: IN read {byte:08b}"

    # 3. The chip selects: 'a', PSRAM A, 'b', PSRAM B, 'c'
    byte = await board.rx.get()
    assert byte == ord("a"), f"got {byte:#04x}, want 'a'"
    falls = list(board.cs_falls)
    byte = await board.rx.get()
    assert byte == ord("b"), f"got {byte:#04x}, want 'b'"
    assert board.cs_falls[1] - falls[1] >= 2 and board.cs_falls[2] == falls[2], (
        f"PSRAM A store and load: uio[6] fell {board.cs_falls[1] - falls[1]} times, "
        f"uio[7] {board.cs_falls[2] - falls[2]}"
    )
    assert board.ram_word(0x100) == 0x1234ABCD, (
        f"PSRAM A holds {board.ram_word(0x100):#010x} at 0x100"
    )
    falls = list(board.cs_falls)
    byte = await board.rx.get()
    assert byte == ord("c"), f"got {byte:#04x}, want 'c'"
    assert board.cs_falls[2] - falls[2] >= 2 and board.cs_falls[1] == falls[1], (
        f"PSRAM B store and load: uio[7] fell {board.cs_falls[2] - falls[2]} times, "
        f"uio[6] {board.cs_falls[1] - falls[1]}"
    )
    assert board.ram_word(0x800100) == 0x89EF4567, (
        f"PSRAM B holds {board.ram_word(0x800100):#010x} at 0x100"
    )

    # 4. Done, and nothing after it
    byte = await board.rx.get()
    assert byte == ord("Z"), f"got {byte:#04x}, want 'Z'"
    await Timer(12 * BIT_NS, unit="ns")
    assert board.rx.empty(), "a byte after the end of the stream"
    assert board.cs_falls[0] > 0 and board.sck_rises > 0, (
        "no flash read on uio[0] and uio[3]"
    )


@cocotb.test(timeout_time=2, timeout_unit="ms")
async def test_pins(dut):
    """Every pin; the QSPI devices answer 2 ns after SCK falls."""
    await pins(dut, rd_late=0, delay_ns=2, hold_ns=1)


@cocotb.test(timeout_time=2, timeout_unit="ms")
async def test_pins_slow_devices(dut):
    """The devices answer just under one SCK period late: the most that
    qspi_rd_late = 0 has to take. 18 ns, not 19: at 19 the data lands 1 ns
    before the sampling edge, and at gate level, where every flop has a 1 ns
    clock-to-output and SCK reaches its pin 1 ns later, it lands in the very
    time step of that edge -- a race inside the simulator, not in the chip."""
    await pins(dut, rd_late=0, delay_ns=18, hold_ns=1)


@cocotb.test(timeout_time=2, timeout_unit="ms")
async def test_pins_rd_late(dut):
    """ui_in[0] high through reset. The devices answer more than one SCK
    period late, which only qspi_rd_late = 1 can read."""
    await pins(dut, rd_late=1, delay_ns=25, hold_ns=12)


# ---------------------------------------------------------------------------
# The flash read modes: firmware/tt_flash.S


def table_checksum():
    """The checksum firmware/tt_flash.S computes over its table of words."""
    with open(os.path.join(FIRMWARE, "tt_flash.S")) as f:
        words = [
            int(w, 16)
            for line in f
            if line.startswith("    .word")
            for w in re.findall(r"0x([0-9A-Fa-f]{8})", line)
        ]
    assert len(words) == 64
    ck = 0x12345678
    for w in words:
        ck = ((((ck << 5) | (ck >> 27)) & 0xFFFFFFFF) + w) & 0xFFFFFFFF
    return ck


# DDR_CAP for this bench: the Pmod model answers 2 ns after SCK, with no pads
DDR_CAP = 1
BLK_N = 512  # instructions in the program's straight-line block


async def get_bytes(board, n):
    return [await board.rx.get() for _ in range(n)]


async def get_word(board):
    return sum(b << (8 * i) for i, b in enumerate(await get_bytes(board, 4)))


async def expect_char(board, ch):
    byte = await board.rx.get()
    assert byte == ord(ch), f"got {byte:#04x}, want {ch!r}"


async def get_phase(board):
    """One run of the program's block and table: (clocks, count, checksum,
    (EBh, EDh commands seen by the flash when the checksum's 'C' arrived))."""
    await expect_char(board, "B")
    await expect_char(board, "E")
    clocks = await get_word(board)
    lo, hi = await get_bytes(board, 2)
    await expect_char(board, "C")
    seen = (int(board.dut.pmod.n_eb.value), int(board.dut.pmod.n_edh.value))
    return clocks, lo | hi << 8, await get_word(board), seen


async def flash_modes(dut, no_stream, cap, check_reset=False):
    """firmware/tt_flash.S with ui_in[2], the no-stream strap, held at
    no_stream through the pin reset and then set to the other level, and the
    DDR capture point cap on ui_in[7:5]. Returns
    the clocks the SDR and the DDR block took."""
    board = Board(dut)
    dut.pmod.delay_ns.value = 2
    dut.pmod.hold_ns.value = 1
    board.load_flash("tt_flash.hex")
    dut.ena.value = 1
    dut.rst_n.value = 1
    dut.uart_rx.value = 1
    dut.gpio_in.value = no_stream << 2 | cap << 5
    board.start()

    # The pin reset, as the demo board's firmware does it: clock stopped.
    await Timer(20, unit="ns")
    board.reset(True)
    await Timer(50, unit="ns")
    board.reset(False)
    await Timer(30, unit="ns")
    board.clock_on = True
    await ClockCycles(dut.clk, 2)
    await Timer(1, unit="ns")
    dut.gpio_in.value = (1 - no_stream) << 2 | cap << 5  # the strap is not read again

    # The UART divisor resets to 34 (114,890 baud at 62.5 MHz); the strap and
    # QSPI_CFG: STREAM = ~strap, DDR 0, DDR_CAP 2.
    dll, dlm, straps, cfg = await get_bytes(board, 4)
    assert (dll, dlm) == (34, 0), f"UART divisor reset {dlm:02x}{dll:02x}, want 0022"
    assert straps == no_stream << 1, f"STRAPS = {straps:#04x}, want {no_stream << 1:#04x}"
    stream = 1 - no_stream
    assert cfg == (2 << 2) | stream, f"QSPI_CFG = {cfg:#04x}, want {(2 << 2) | stream:#04x}"

    want_ck = table_checksum()
    eb0, edh0 = int(dut.pmod.n_eb.value), int(dut.pmod.n_edh.value)  # the model counts across tests

    # SDR: no EDh command at all
    sdr_clocks, count, ck, (eb, edh) = await get_phase(board)
    assert count == BLK_N, f"SDR block ran {count} instructions, want {BLK_N}"
    assert ck == want_ck, f"SDR checksum {ck:#010x}, want {want_ck:#010x}"
    assert edh == edh0, f"{edh - edh0} EDh commands before DDR was switched on"
    assert eb > eb0, "no EBh command seen"

    # DDR on: QSPI_CFG.DDR reads back set, and from here no EBh command
    await expect_char(board, "d")
    cfg_ddr = await board.rx.get()
    want_cfg = (cfg & 0xE3) | cap << 2 | 2
    assert cfg_ddr == want_cfg, f"QSPI_CFG = {cfg_ddr:#04x} after DDR on, want {want_cfg:#04x}"
    eb_ddr = int(dut.pmod.n_eb.value)
    ddr_clocks, count, ck, (eb, edh) = await get_phase(board)
    assert count == BLK_N, f"DDR block ran {count} instructions, want {BLK_N}"
    assert ck == want_ck, f"DDR checksum {ck:#010x}, want {want_ck:#010x}"
    assert edh > edh0, "no EDh command seen with DDR on"
    assert eb - eb_ddr <= 1, f"{eb - eb_ddr} EBh commands after DDR on"
    await expect_char(board, "Z")
    dut._log.info(
        f"no_stream={no_stream}: block clocks SDR {sdr_clocks} DDR {ddr_clocks}; "
        f"flash CS falls {board.cs_falls[0]}, EBh {int(dut.pmod.n_eb.value)}, "
        f"EDh {int(dut.pmod.n_edh.value)}, resumes {int(dut.pmod.n_resume.value)}"
    )

    if check_reset:
        # Any reset returns the flash reads to SDR. The program is spinning in
        # flash with DDR on; the pin reset comes with the clock running.
        await ClockCycles(dut.clk, 300)
        await Timer(3, unit="ns")
        board.reset(True)
        dut.gpio_in.value = no_stream << 2 | cap << 5
        await Timer(2, unit="ns")
        edh_at_reset = int(dut.pmod.n_edh.value)
        await ClockCycles(dut.clk, 6)
        await Timer(1, unit="ns")
        board.reset(False)
        await ClockCycles(dut.clk, 2)
        await Timer(1, unit="ns")
        dut.gpio_in.value = (1 - no_stream) << 2 | cap << 5
        while not board.rx.empty():
            board.rx.get_nowait()
        dll, dlm, straps, cfg = await get_bytes(board, 4)
        assert cfg == (2 << 2) | stream, f"QSPI_CFG = {cfg:#04x} after the reset, want SDR"
        assert int(dut.pmod.n_edh.value) == edh_at_reset, "EDh read after the reset"
    return sdr_clocks, ddr_clocks


@cocotb.test(timeout_time=8, timeout_unit="ms")
async def test_stream_on(dut):
    """ui_in[2] low through reset: flash reads stream, DDR reads work."""
    sdr, ddr = await flash_modes(dut, no_stream=0, cap=DDR_CAP, check_reset=True)
    assert sdr < 24 * BLK_N, f"streaming SDR block took {sdr} clocks"


@cocotb.test(timeout_time=8, timeout_unit="ms")
async def test_stream_off(dut):
    """ui_in[2] high through reset: no streaming, and slower flash reads."""
    sdr, ddr = await flash_modes(dut, no_stream=1, cap=DDR_CAP)
    assert sdr > 32 * BLK_N, f"SDR block without streaming took only {sdr} clocks"
