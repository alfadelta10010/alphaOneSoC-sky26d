# The flash read modes of the chip, from the outside (test_stream_on,
# test_stream_off and test_ddr in ../test.py). The program reports through
# the UART and nothing else.
#
# Output, in order (LE words):
#   divisor reset value DLL, DLM   (read before the program sets it)
#   syscon STRAPS, QSPI_CFG        (as they stand after the pin reset)
#   'B' 'E' clocks(4) count(2)     a straight-line block of BLK_N instructions
#                                  run from flash: mtime clocks it took, and
#                                  the number of instructions that ran
#   'C' checksum(4)                the TABLE_N words of the table below, read
#                                  with loads
#   'd' QSPI_CFG                   after DDR is switched on, with DDR_CAP
#                                  taken from ui_in[7:5]
#   'B' 'E' ... 'C' ...            the same block and table, with DDR on
#   'Z'                            then the program spins in flash
#
# The divisor is set to 1, 16 clocks a bit, which is the rate the testbench's
# UART runs at. The checksum is s = rotl(s, 5) + w from s = 0x12345678.
#include "periph.h"
#define SYSCON  0x10020000
#define S_STRAPS 0x10
#define S_QCFG   0x1C
#define TABLE_N 64
#define BLK_N   512

/* Send r and wait until its stop bit has gone (clobbers t4, t5). */
.macro PUTC r
    sb   \r, THR(s0)
    WAIT_LSR s0, LSR_TEMT
.endm
/* Send the 32-bit register r, low byte first (clobbers t3, t4, t5). */
.macro PUTW r
    mv   t3, \r
    PUTC t3
    srli t3, \r, 8
    PUTC t3
    srli t3, \r, 16
    PUTC t3
    srli t3, \r, 24
    PUTC t3
.endm

    .section .text.init
    .globl _start
_start:
    li   s0, UART
    li   s1, MTIME
    li   s2, SYSCON
    li   t0, 0x80
    sb   t0, LCR(s0)             # DLAB
    lbu  s3, DLL(s0)             # the reset divisor
    lbu  s4, DLM(s0)
    li   t0, 1
    sb   t0, DLL(s0)
    sb   zero, DLM(s0)
    sb   zero, LCR(s0)
    li   t0, GPIO
    sw   zero, G_CTRL(t0)        # SPI transmitter off
    PUTC s3
    PUTC s4
    lw   t0, S_STRAPS(s2)
    PUTC t0
    lw   s5, S_QCFG(s2)
    PUTC s5

    jal  ra, phase               # SDR

    li   t0, GPIO                # DDR_CAP from ui_in[7:5]: the testbench's round trip
    lw   t0, G_IN(t0)
    srli t0, t0, 5
    andi t0, t0, 7
    slli t0, t0, 2
    andi s5, s5, 0xE3            # clear DDR_CAP (bits 4:2)
    or   s5, s5, t0
    ori  s5, s5, 2               # QSPI_CFG.DDR on; STREAM as it is
    sw   s5, S_QCFG(s2)
    lw   t0, S_QCFG(s2)
    li   t1, 'd'
    PUTC t1
    PUTC t0

    jal  ra, phase               # DDR

    li   t1, 'Z'
    PUTC t1
spin:
    j    spin

    .text
phase:
    mv   s11, ra
    li   t1, 'B'
    PUTC t1
    li   a0, 0
    lw   s6, 0(s1)
    jal  ra, blk
    lw   s7, 0(s1)
    sub  s7, s7, s6
    li   t1, 'E'
    PUTC t1
    PUTW s7
    PUTC a0
    srli t2, a0, 8
    PUTC t2
    la   a1, table
    li   a2, TABLE_N
    li   a3, 0x12345678
1:  lw   a4, 0(a1)
    slli a5, a3, 5
    srli a3, a3, 27
    or   a3, a3, a5
    add  a3, a3, a4
    addi a1, a1, 4
    addi a2, a2, -1
    bnez a2, 1b
    li   t1, 'C'
    PUTC t1
    PUTW a3
    jr   s11

    .option push
    .option norvc
    .align 2
blk:
    .rept BLK_N
    addi a0, a0, 1
    .endr
    ret
    .option pop

    .section .rodata
    .align 2
table:
    .word 0x00000000, 0xFFFFFFFF, 0xA5A5A5A5, 0x5A5A5A5A
    .word 0x0F0F0F0F, 0xF0F0F0F0, 0x80000001, 0x7FFFFFFE
    .word 0xE29724BC, 0x8D1AB8EB, 0x1B6AF94E, 0x98D0B055
    .word 0x5D96C5B0, 0x5E0B1D4F, 0x4D63EA62, 0xDD76E659
    .word 0x59F11BE4, 0x980E35F3, 0xE36182B6, 0x663D1A9D
    .word 0x5F78DB58, 0xA88F26D7, 0xA02C964A, 0xCFCE1121
    .word 0x90F1F80C, 0x3AB953FB, 0x42D1391E, 0x91BECDE5
    .word 0xC485A600, 0xAD5C615F, 0x5B32BF32, 0xC21294E9
    .word 0x09765934, 0x95103303, 0x3DDFBC86, 0xEEFEEA2D
    .word 0xCF13C5A8, 0xEE98ECE7, 0x6B26051A, 0x52EF91B1
    .word 0x20EEDF5C, 0xE58AF30B, 0xFD66ACEE, 0xE6CA8F75
    .word 0xAC4DDA50, 0x532EE96F, 0xF2AA0802, 0x16742779
    .word 0x82E02A84, 0x59A5B413, 0x6573AA56, 0x1B92DDBD
    .word 0xCEB283F8, 0xBF4C76F7, 0x08D667EA, 0x42937641
    .word 0xEB62DAAC, 0xEE60961B, 0x7BC854BE, 0x9DECF505
    .word 0x989462A0, 0xBCE3B57F, 0x47B6C4D2, 0xEBA49E09
