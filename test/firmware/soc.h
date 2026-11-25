/* Definitions for the test programs that talk to test.py through the UART
 * (cache.S, gpio_irq.S, pinmux.S). Included after periph.h.
 *
 * The chip's pins are all the testbench sees, so a program reports on the
 * UART as framed messages, and the testbench acts on the pins on a cue:
 *
 *   0x10 code       a cue: the testbench does something at the pins, and the
 *                   program waits CUE_WAIT clocks for it to land (CUE)
 *   0x11 w0..w3     VALUE: a word, little-endian, for the testbench to check
 *   0x12 w0..w3     after a failed check: the value the check saw
 *   0x13 w0..w3     the end: 0x5555 pass, (code << 16) | 0x3333 fail. The
 *                   program then writes it to the system controller, which
 *                   powers the chip off.
 *
 * Any other byte on the UART is the program's own traffic. s11 = SYSCON,
 * s2 = PLIC base and a4 = PLIC context base in the interrupt programs. The
 * interrupt programs poll mip.MEIP with mstatus.MIE off, so the PLIC's claim
 * and complete sequence is the only interrupt plumbing under test.
 */
#include "periph.h"
#define SYSCON    0x10020000
#define PINMUX    0x10020020      /* pin i's code in bits [4i+2:4i] */
#define CACHE_CTL 0x10020024
#define PLIC      0x0C000000
#define PL_PRIO   0x04            /* source n at PL_PRIO * n */
#define PL_EN     0x2000
#define PL_CTX    0x200000        /* threshold +0, claim / complete +4 */
#define PWM       0x10030000
#define AUDIO     0x10030100
#define SRC_UART  1
#define SRC_GPIO  4
#define PWM_CFG   0x00
#define PWM_CMP0  0x20
#define AU_TONE0  0x00
#define AU_CTRL   0x10
#define FINISH_PASS 0x5555
#define FINISH_FAIL 0x3333
/* The UART runs at divisor 1 (16 clocks a bit, 160 a character) in these programs. */
#define CHAR_CLKS 160
#define CUE_WAIT  3000

/* r == v, or fail with `code` (clobbers t5, a6, a7) */
.macro CHECK r, v, code
    li   t5, \v
    beq  \r, t5, 88f
    mv   a7, \r
    li   a6, \code
    j    test_fail
88:
.endm
.macro CHECKR r1, r2, code
    beq  \r1, \r2, 88f
    mv   a7, \r1
    li   a6, \code
    j    test_fail
88:
.endm

/* Frames. These clobber t4, t5 and t6. */
.macro SOC_TEMT
    li   t6, UART
89: lbu  t5, LSR(t6)
    andi t5, t5, LSR_TEMT
    beqz t5, 89b
.endm
.macro SOC_PUT r                  /* t6 = UART; sends the low byte of r */
89: lbu  t5, LSR(t6)
    andi t5, t5, LSR_THRE
    beqz t5, 89b
    sb   \r, THR(t6)
.endm
.macro FRAME tag, r
    SOC_TEMT
    li   t4, \tag
    SOC_PUT t4
    SOC_PUT \r
    srli t4, \r, 8
    SOC_PUT t4
    srli t4, \r, 16
    SOC_PUT t4
    srli t4, \r, 24
    SOC_PUT t4
    SOC_TEMT
.endm
.macro CUE_NW code                /* the cue frame alone, no wait */
    SOC_TEMT
    li   t4, 0x10
    SOC_PUT t4
    li   t4, \code
    SOC_PUT t4
    SOC_TEMT
.endm
.macro CUE code, n                /* a cue, then n clocks for the action to land */
    CUE_NW \code
    DELAY \n
.endm
.macro VALUE r
    FRAME 0x11, \r
.endm
/* Every program starts here: the divisor 1 and the system controller's base. */
.macro SOC_INIT
    li   s11, SYSCON
    li   t0, UART
    li   t1, 0x80
    sb   t1, LCR(t0)
    li   t1, 1
    sb   t1, DLL(t0)
    sb   zero, DLM(t0)
    sb   zero, LCR(t0)
.endm
/* The UART sent its last stop bit and the SPI shifter is idle (clobbers t4, t5, t6). */
.macro DRAIN
    li   t6, UART
    WAIT_LSR t6, LSR_TEMT
    li   t6, GPIO
    lw   t5, G_OUT(t6)
    sw   t5, G_OUT(t6)
.endm
/* test_pass / test_fail, once per program */
.macro EPILOGUE
test_fail:
    FRAME 0x12, a7
    slli a6, a6, 16
    li   t5, FINISH_FAIL
    or   a6, a6, t5
    j    87f
test_pass:
    li   a6, FINISH_PASS
87:
    DRAIN
    FRAME 0x13, a6
    sw   a6, 0(s11)
1:  j    1b
.endm

/* PLIC: priorities 1 for sources 1..9, enable word = mask, threshold 0, mie.MEIE
 * set with mstatus.MIE clear. Sets s2 = PLIC, a4 = context base. Clobbers t0-t2. */
.macro PLIC_SETUP mask
    li   s2, PLIC
    li   a4, PLIC + PL_CTX
    li   t0, 1
    li   t1, 9
    addi t2, s2, PL_PRIO
87: sw   t0, 0(t2)
    addi t2, t2, 4
    addi t1, t1, -1
    bnez t1, 87b
    li   t2, PLIC + PL_EN
    li   t0, \mask
    sw   t0, 0(t2)
    sw   zero, 0(a4)
    li   t0, 0x800
    csrw mie, t0
.endm
/* Wait (bounded) for mip.MEIP, else fail `code` (clobbers t4, t5, a6, a7) */
.macro WAIT_MEIP code
    li   t4, 400000
89: csrr t5, mip
    srli t5, t5, 11
    andi t5, t5, 1
    bnez t5, 88f
    addi t4, t4, -1
    bnez t4, 89b
    li   a7, 0
    li   a6, \code
    j    test_fail
88:
.endm
.macro NO_MEIP code               /* MEIP must be clear (clobbers t5, a6, a7) */
    csrr t5, mip
    srli t5, t5, 11
    andi t5, t5, 1
    CHECK t5, 0, \code
.endm
.macro CLAIM id, code             /* the claim must return `id` (t0 = claim) */
    lw   t0, 4(a4)
    CHECK t0, \id, \code
.endm
.macro COMPLETE
    sw   t0, 4(a4)
.endm
