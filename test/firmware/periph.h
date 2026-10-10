/* Addresses, register offsets and helper macros for the test programs.
 *
 * The programs boot from flash (link.ld) and report over the UART and the
 * GPIO pins, which is all the testbench can see of the chip.
 */
#define UART      0x10000000
#define GPIO      0x10010000
#define MTIMECMP  0x02004000
#define MTIME     0x0200BFF8

/* UART offsets and bits (16550) */
#define RBR 0
#define THR 0
#define DLL 0
#define IER 1
#define DLM 1
#define IIR 2
#define FCR 2
#define LCR 3
#define MCR 4
#define LSR 5
#define MSR 6
#define SCR 7
#define LSR_DR   0x01
#define LSR_OE   0x02
#define LSR_THRE 0x20
#define LSR_TEMT 0x40

/* GPIO registers */
#define G_OUT  0x0
#define G_IN   0x4
#define G_DATA 0x8
#define G_CTRL 0xC

/* Spin until mtime has advanced by n clocks (clobbers t4, t5, t6). */
.macro DELAY n
    li   t6, MTIME
    lw   t5, 0(t6)
    li   t4, \n
    add  t4, t4, t5
89: lw   t5, 0(t6)
    blt  t5, t4, 89b
.endm
/* Wait until LSR has all of `bits` (base register b; clobbers t4, t5). */
.macro WAIT_LSR b, bits
89: lbu  t5, LSR(\b)
    andi t5, t5, \bits
    li   t4, \bits
    bne  t5, t4, 89b
.endm
