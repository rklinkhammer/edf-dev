# Arguments are passed as argv, never substituted into Tcl source.
if {[llength $argv] != 3} {error "Expected project.xpr output-directory jobs"}
lassign $argv project output jobs
open_project $project
if {[get_property PART [current_project]] ne "xc7z020clg400-1"} {error "Expected Arty Z7-20 part xc7z020clg400-1"}
save_project_as -exclude_run_results edf_arty [file join $output project]
# Work only in the saved project. Keep original source/IP revisions; no automatic upgrades.
close_project
open_project [file join $output project edf_arty.xpr]
reset_run synth_1
launch_runs synth_1 -jobs $jobs
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {error "Synthesis failed"}
launch_runs impl_1 -to_step write_bitstream -jobs $jobs
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {error "Implementation/bitstream failed"}
open_run impl_1
report_io -file [file join $output io.rpt]
report_timing_summary -file [file join $output timing.rpt]
report_drc -file [file join $output drc.rpt]
foreach delay {max min} {
    set paths [get_timing_paths -delay_type $delay -max_paths 1]
    if {![llength $paths]} {error "No $delay timing paths: review constraints"}
    if {[get_property SLACK $paths] < 0} {error "$delay timing failed; see timing.rpt"}
}
if {[llength [get_drc_violations -filter {SEVERITY == Error}]]} {error "DRC errors; see drc.rpt"}
write_hw_platform -fixed -include_bit -force -file [file join $output dvrmc.xsa]
close_project
