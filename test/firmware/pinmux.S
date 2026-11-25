# The pinmux (0x1002_0020), the UART's RTS#, the PWM and the audio voice at the pins (test_pinmux in
# ../test.py). Only pin 5 code 2 (RTS#) and pin 6 code 4 (PWM0) are legal; any other
# code on any pin stores 0 (WARL) and reads 0. Pin 7 is PWM1 always (no code): it also plays the tone.
#   1  read-back: every code 0..7 on every pin (word code * 0x11111111) reads back 0x00200000 for code 2,
#      0x04000000 for 4 and 0 for the others (pin 7 has no code) (bit 4i+3 reads 0); reset value 0.
#   2  RTS# on uo_out[5] (code 2, giving up the SD card's CS#), interrupts off, the FIFO on. Cue 1: the
#      testbench pastes 64 characters (0x20 + (7n + 3) mod 95), sending one only while uo_out[5] is low (as a
#      sender with CTS flow control does). First the program reads nothing for 24 character times: the 8-deep
#      FIFO fills, RTS# goes high at 7 entries and the testbench holds the rest (cue 8: it checks uo_out[5]
#      high and 7 to 10 characters sent). Then the program drains, slowly (3 character times between pops):
#      the paste resumes, 64 in order, none lost, no overrun.
#   3  back to the default: uo_out[5] = GPIO OUT bit 5 (SD CS#): cue 2 with OUT bit 5 low.
#   4  illegal codes (pin 4 = 2, pin 5 = 4, pin 6 = 2, pin 7 = 4) read back 0: cue 3, the default map holds
#      (uo_out[5] high, [6] and [7] low).
#   5  PWM0 on pin 6 (code 4, cfg = enalways, cmp0 0xBFFF): cue 6, the testbench measures the 25 % duty on
#      uo_out[6]; cue 7 after the pinmux is 0 again (uo_out[6] low).
#   6  PWM1 on pin 7 (fixed, cmp1 0xBFFF, cmp0 stays 0xFFFF): cue 4, 25 % duty on uo_out[7]; cue 5 with the
#      PWM off and cmp1 back at 0xFFFF (pin 7 low).
#   7  Tone on PWM1: A4 = scale 2, cmp0 35511, cmp1 17755, zerocmp (a period of 35511 * 4 + 1 = 142045 clocks):
#      cue 9, the testbench measures the period on uo_out[7]; tone off: cue 10, low.
#include "soc.h"
    .section .text.init
    .globl _start
_start:
    SOC_INIT
    li   s1, PINMUX
    li   s0, UART
    lw   t0, 0(s1)
    CHECK t0, 0, 0x01
    li   t2, 0
    li   t3, 8
1:  li   t1, 0x11111111
    mul  t1, t1, t2
    sw   t1, 0(s1)
    lw   t0, 0(s1)
    li   t4, 0
    li   t5, 2
    bne  t2, t5, 4f
    li   t4, 0x00200000
4:  li   t5, 4
    bne  t2, t5, 5f
    li   t4, 0x04000000
5:  CHECKR t0, t4, 0x02
    addi t2, t2, 1
    bne  t2, t3, 1b
    sw   zero, 0(s1)

    # RTS# on pin 5, the paste with flow control
    li   t0, 0x00200000
    sw   t0, 0(s1)
    lw   t1, 0(s1)
    CHECK t1, 0x00200000, 0x03
    li   t0, 0x01
    sb   t0, FCR(s0)              # FIFO on (RTS# asserts while two or more entries are free)
    li   s3, 0                    # received
    li   s4, 0                    # mismatches
    CUE 1, 100
    DELAY (24 * CHAR_CLKS)        # read nothing: RTS# must stop the paste
    CUE 8, 100
    li   s5, 4000
2:  lbu  t1, LSR(s0)
    andi t2, t1, 2
    CHECK t2, 0, 0x04             # no overrun
    andi t2, t1, 1
    bnez t2, 3f
    addi s5, s5, -1
    bnez s5, 2b
    j    4f                       # nothing more is coming
3:  lbu  t1, RBR(s0)
    li   t2, 7
    mul  t2, s3, t2
    addi t2, t2, 3
    li   t3, 95
    remu t2, t2, t3
    addi t2, t2, 0x20
    beq  t2, t1, 5f
    addi s4, s4, 1
5:  addi s3, s3, 1
    li   t2, 64
    beq  s3, t2, 4f
    li   s5, 4000
    DELAY (3 * CHAR_CLKS)
    j    2b
4:  CHECK s3, 64, 0x05
    CHECK s4, 0, 0x06
    # default map again: pin 5 = OUT bit 5
    sw   zero, 0(s1)
    li   s2, GPIO
    lw   t0, G_OUT(s2)
    andi t0, t0, 0x20
    CHECK t0, 0x20, 0x07          # reset 0xB9: bit 5 high
    lw   t0, G_OUT(s2)
    andi t0, t0, 0xDF
    sw   t0, G_OUT(s2)
    CUE 2, 400                    # testbench: uo_out[5] low
    lw   t0, G_OUT(s2)
    ori  t0, t0, 0x20
    sw   t0, G_OUT(s2)
    DELAY 400
    # illegal codes: pin 4 = 2, pin 5 = 4, pin 6 = 2, pin 7 = 4 all store 0
    li   t0, (2 << 16) | (4 << 20) | (2 << 24) | (4 << 28)
    sw   t0, 0(s1)
    lw   t0, 0(s1)
    CHECK t0, 0, 0x08
    CUE 3, 400                    # testbench: uo_out[5] high, [6] and [7] low
    sw   zero, 0(s1)
    # PWM0 on pin 6
    li   s6, PWM
    li   t0, 0xBFFF
    sw   t0, PWM_CMP0(s6)
    li   t0, 4 << 24
    sw   t0, 0(s1)
    li   t0, 0x1000
    sw   t0, PWM_CFG(s6)
    CUE 6, 3 << 16
    sw   zero, PWM_CFG(s6)
    sw   zero, 0(s1)
    li   t0, 0xFFFF
    sw   t0, PWM_CMP0(s6)
    CUE 7, 400
    # PWM1 on pin 7
    li   t0, 0xBFFF
    sw   t0, PWM_CMP0+4(s6)
    li   t0, 0x1000
    sw   t0, PWM_CFG(s6)
    CUE 4, 3 << 16
    sw   zero, PWM_CFG(s6)
    li   t0, 0xFFFF
    sw   t0, PWM_CMP0+4(s6)
    sw   zero, 8(s6)
    CUE 5, 400                    # pin 7 low
    # Tone: A4 on PWM1
    sw   zero, PWM_CFG(s6)
    li   t0, 17755
    sw   t0, PWM_CMP0+4(s6)
    li   t0, 35511
    sw   t0, PWM_CMP0(s6)
    sw   zero, 8(s6)
    li   t0, 0x1202
    sw   t0, PWM_CFG(s6)
    CUE 9, 3 * 142045
    sw   zero, PWM_CFG(s6)
    li   t0, 0xFFFF
    sw   t0, PWM_CMP0+4(s6)
    sw   t0, PWM_CMP0(s6)
    sw   zero, 8(s6)
    CUE 10, 400
    j    test_pass
    EPILOGUE
