# Zybo EDF integration checks — 2026-11-08

- 46 host tests: 43 passed, three runtime tests skipped (EDF_RUNTIME_TEST/container required).
- New tests exercise 1 GiB memory and PS UART requirements, repeatable console aliases,
  board-isolated import, rejection of mismatched SDT/manifest and HALT overlay binding.
- Arty and Zybo full-build dry runs pass. Shell/Python syntax and diff checks pass.
- dmotor Vivado build-mode validation/output products/wrapper generation passed on
  the user-wired source before adding the strict package-pin preflight.
- The strict preflight correctly rejects missing bumper_fault and auxiliary PL UART
  pin assignments before expensive synthesis. The owner has been asked to select pins
  or remove the unused auxiliary UART.

No complete routed Zybo XSA, generated SDT bundle, BitBake image/WIC or hardware boot
is claimed. The implementation provides the workflow; first end-to-end execution
remains pending pin completion. Existing user changes to Arty generated hardware
inputs and semantic-test recipe were retained.

## Pin assignment follow-up

The user selected bumper_fault on JD/P14 and authorized any remaining JD pins
for the auxiliary PL UART. TX is now JD7/U14; RX is JD8/U15 (LVCMOS33).
`check_zybo_interface.py --require-pins` passes with no pending assignments or
duplicate pins. The earlier preflight rejection above is historical; physical
validation and the complete routed/image build remain pending.
