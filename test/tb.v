`default_nettype none
`timescale 1ns / 1ps

/* The chip on its board, for the cocotb tests in test.py.

   The tests reach the design through its pins only, so the same testbench
   runs on the RTL and on the gate-level netlist. Around the pins:

   - the Tiny Tapeout QSPI Pmod (qspi_pmod_model.v) on uio. A pin the chip is
     not driving does what it does on the Pmod: the chip selects are pulled
     up, SCK and SD0..SD3 float (X);
   - the UART, which test.py drives and decodes: uart_rx is ui_in[3],
     uart_tx is uo_out[4] and uart_rts_n is uo_out[5];
   - gpio_in, the other seven ui_in pins. ui_in[0] is also the qspi_rd_late
     strap while reset is held.
*/
module tb ();

  // Dump the signals to a FST file. You can view it with gtkwave or surfer.
  initial begin
    $dumpfile("tb.fst");
    $dumpvars(0, tb);
    #1;
  end

  // Wire up the inputs and outputs:
  reg clk;
  reg rst_n;
  reg ena;
  reg [7:0] gpio_in;  // ui_in; bit 3 is not used, that pin is uart_rx
  reg uart_rx;
  wire [7:0] ui_in = {gpio_in[7:4], uart_rx, gpio_in[2:0]};
  wire [7:0] uio_in;
  wire [7:0] uo_out;
  wire [7:0] uio_out;
  wire [7:0] uio_oe;
`ifdef GL_TEST
  wire VPWR = 1'b1;
  wire VGND = 1'b0;
`endif

  tt_um_alfadelta10010_alphaone_soc user_project (

      // Include power ports for the Gate Level test:
`ifdef GL_TEST
      .VPWR(VPWR),
      .VGND(VGND),
`endif

      .ui_in  (ui_in),    // Dedicated inputs
      .uo_out (uo_out),   // Dedicated outputs
      .uio_in (uio_in),   // IOs: Input path
      .uio_out(uio_out),  // IOs: Output path
      .uio_oe (uio_oe),   // IOs: Enable path (active high: 0=input, 1=output)
      .ena    (ena),      // enable - goes high when design is selected
      .clk    (clk),      // clock
      .rst_n  (rst_n)     // not reset
  );

  // The dedicated outputs by name.
  wire uart_tx = uo_out[4];
  wire uart_rts_n = uo_out[5];
  wire [5:0] gpio_out = {uo_out[7:6], uo_out[3:0]};  // GPIO OUT 7:6 and 3:0

  // The QSPI Pmod. SD0..SD3 are uio[1], [2], [4], [5], and each pin has its
  // own output enable.
  wire [3:0] pmod_io;
  wire pmod_oe;
  wire [3:0] sd_out = {uio_out[5], uio_out[4], uio_out[2], uio_out[1]};
  wire [3:0] sd_oe = {uio_oe[5], uio_oe[4], uio_oe[2], uio_oe[1]};
  wire [3:0] host_io = {
    sd_oe[3] ? sd_out[3] : 1'bx,
    sd_oe[2] ? sd_out[2] : 1'bx,
    sd_oe[1] ? sd_out[1] : 1'bx,
    sd_oe[0] ? sd_out[0] : 1'bx
  };
  wire [3:0] sd_pin = pmod_oe ? pmod_io : host_io;

  // SCK and the chip selects as they are at the pins.
  wire qspi_cs0_n = uio_oe[0] ? uio_out[0] : 1'b1;  // flash, pulled up
  wire qspi_cs1_n = uio_oe[6] ? uio_out[6] : 1'b1;  // PSRAM A, pulled up
  wire qspi_cs2_n = uio_oe[7] ? uio_out[7] : 1'b1;  // PSRAM B, pulled up
  wire qspi_sck = uio_oe[3] ? uio_out[3] : 1'bx;  // floats

  assign uio_in = {
    qspi_cs2_n, qspi_cs1_n, sd_pin[3], sd_pin[2], qspi_sck, sd_pin[1], sd_pin[0], qspi_cs0_n
  };

  qspi_pmod_model pmod (
      .host_sck   (uio_out[3]),
      .host_cs_n  ({uio_out[7], uio_out[6], uio_out[0]}),
      .host_ctl_oe(uio_oe[3]),
      .host_io    (host_io),
      .host_oe    (&sd_oe),
      .dev_io     (pmod_io),
      .dev_oe     (pmod_oe)
  );

endmodule
