# Makefile
# See https://docs.cocotb.org/en/stable/quickstart.html for more info

# defaults
SIM ?= icarus
FST ?= -fst # Use more efficient FST format
TOPLEVEL_LANG ?= verilog
SRC_DIR = $(PWD)/../src
PROJECT_SOURCES = tt_um_alfadelta10010_alphaone_soc.v \
                  alphaone_soc.v \
                  fyracore.v \
                  alu.v \
                  branchCtrl.v \
                  clint.v \
                  compressed_decoder.v \
                  controller.v \
                  csr.v \
                  decoder.v \
                  muldiv.v \
                  pmp.v \
                  regFile.v \
                  rf_top.v \
                  signExt.v \
                  qspi_ctrl.v \
                  mem_ctrl.v \
                  soc_bus.v \
                  uart.v \
                  gpio.v

ifneq ($(GATES),yes)

# RTL simulation:
SIM_BUILD				= sim_build/rtl
VERILOG_SOURCES += $(addprefix $(SRC_DIR)/,$(PROJECT_SOURCES))

else

# Gate level simulation:
SIM_BUILD				= sim_build/gl
COMPILE_ARGS    += -DGL_TEST
COMPILE_ARGS    += -DFUNCTIONAL
COMPILE_ARGS    += -DUSE_POWER_PINS
COMPILE_ARGS    += -DSIM
COMPILE_ARGS    += -DUNIT_DELAY=\#1
VERILOG_SOURCES += $(PDK_ROOT)/sky130A/libs.ref/sky130_fd_sc_hd/verilog/primitives.v
VERILOG_SOURCES += $(PDK_ROOT)/sky130A/libs.ref/sky130_fd_sc_hd/verilog/sky130_fd_sc_hd.v

# this gets copied in by the GDS action workflow
VERILOG_SOURCES += $(PWD)/gate_level_netlist.v

# The register file macro is a cell of the netlist; its model comes from src/.
VERILOG_SOURCES += $(SRC_DIR)/rf_top.v

endif

# The register file macro has no reset: start its words at X, as on the chip,
# not at the zeros the model would otherwise give. And make the macro answer X
# to a read of the word written on the same edge, whose timing its views do not
# give: the design serves that case from a bypass of its own and must not use
# the macro's answer.
PLUSARGS        += +RF_X +RF_COLLIDE_X

# Allow sharing configuration between design and testbench via `include`:
COMPILE_ARGS 		+= -I$(SRC_DIR)

# Include the testbench sources:
VERILOG_SOURCES += $(PWD)/qspi_pmod_model.v
VERILOG_SOURCES += $(PWD)/tb.v
TOPLEVEL = tb

# List test modules to run, separated by commas and without the .py suffix:
COCOTB_TEST_MODULES = test

# include cocotb's make rules to take care of the simulator setup
include $(shell cocotb-config --makefiles)/Makefile.sim
