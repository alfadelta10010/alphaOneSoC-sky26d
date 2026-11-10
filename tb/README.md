# Formal checks and riscv-formal

This directory holds checks that sit beside the TinyTapeout cocotb tests in
`test/`. Neither set runs in TinyTapeout's CI; run them by hand.

* `tb/formal/` -- property harnesses (`*_props.sv`) for the core (`fyracore`),
  the CSR block, the multiplier/divider, the memory controller with the QSPI
  controller (streaming on, off and toggling; SDR property list), the QSPI
  controller's own pin-level rules including the DDR read (`qspi_pins`), the
  SoC bus, the SPI controller and the system controller. Each
  is proved by k-induction or by pdr from a free power-up state (verdict
  PROVED), checked by bounded model checking from reset (verdict BOUNDED), or
  is a cover (verdict COVERED). `run.sh` is the driver; a sidecar
  `<name>.conf` adds a harness, and `<name>.nonvac` lists broken copies of the
  RTL that the harness must reject. `bounds_tb.v` is not a harness: it
  measures the memory path's latencies (LP LF S LD LI) by random simulation.
* `tb/rvfi/` -- the core's RVFI port (compiled only under `RISCV_FORMAL`, zero
  area when it is off) and the riscv-formal wrapper, check list
  (`checks.cfg`), runner and fault runner. `RESULTS.md` has the recorded
  results and what is not covered.
* `tb/mutate/mutants.py` -- the fault catalogue (data only). `run.sh --nonvac`
  and `tb/rvfi/mutants.sh` read it to build the broken copies.

## Tools

The OSS CAD Suite (https://github.com/YosysHQ/oss-cad-suite-build) provides
yosys, sby, bitwuzla, yices and boolector. Source its `environment` file, or
put its `bin` directory in `FORMAL_BIN` for `tb/formal/run.sh`. riscv-formal
(https://github.com/YosysHQ/riscv-formal) is cloned by `tb/rvfi/run.sh` to
`build/riscv-formal` at the pinned commit, or pass `RVFORMAL=<checkout>`.

## Running

    bash tb/formal/run.sh                      # every harness
    bash tb/formal/run.sh csr core_fetch bus   # some of them
    bash tb/formal/run.sh --nonvac csr         # the broken copies must FAIL
    iverilog -g2012 -DDFN=4 -o bounds_tb src/mem_ctrl.v src/qspi_ctrl.v \
        tb/formal/bounds_tb.v && vvp bounds_tb # measured latencies, not a proof

    bash tb/rvfi/run.sh --list                 # the riscv-formal checks
    ONLY=insn_add_ch0 bash tb/rvfi/run.sh      # one check
    bash tb/rvfi/run.sh RVFORMAL=<checkout>    # the whole list (long)
    bash tb/rvfi/mutants.sh <ID> <check>...    # a fault must make a check FAIL
    bash tb/rvfi/zero_area.sh <git revision>   # RVFI port adds no logic when off

## Verdict words

* `PROVED` -- k-induction closed (length 1 unless the harness says more), pdr
  closed from a free power-up state, or a structural walk found nothing.
* `BOUNDED` -- no counterexample within the stated depth from reset; not a proof
  for longer histories. Every riscv-formal PASS is BOUNDED.
* `COVERED k/k` -- every cover point of the harness was reached.
* `FAILED` -- a counterexample exists.
* `ERROR` -- no verdict (tool error, timeout, or an undriven/implicit wire in a
  harness). It never counts as a pass or as a kill.
* `NONVAC-OK` -- every broken copy was rejected; `NONVAC-MISS` -- one was not,
  so the harness may be vacuous.

`src/fyracore.v` also builds without the port: `tb/rvfi/strip_ifdef.py` removes
the `RISCV_FORMAL` regions and the result must equal the file as built for the
chip.
