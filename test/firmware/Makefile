# Test programs for the chip, built into flash images (Verilog hex, one byte
# per entry, addresses relative to the start of flash).
#
# The .hex files are checked in, so running the tests needs no RISC-V
# toolchain. After changing a .S, run `make` here and commit the .hex with it.

TOOLCHAIN ?= riscv64-unknown-elf-
PROGRAMS  := tt_pins

all: $(PROGRAMS:=.hex)

%.elf: %.S periph.h link.ld
	$(TOOLCHAIN)gcc -march=rv32imac_zicsr_zifencei -mabi=ilp32 -nostdlib -nostartfiles \
		-T link.ld -I. $< -o $@

%.hex: %.elf
	$(TOOLCHAIN)objcopy -O verilog -j .text.init -j .text -j .rodata \
		--change-addresses=-0x20000000 $< $@

clean:
	rm -f *.elf

.PHONY: all clean
.PRECIOUS: %.elf
