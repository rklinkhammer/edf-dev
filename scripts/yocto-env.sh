# Source only, after the per-target lock has been acquired.
source /opt/edf-config/targets.sh || return
edf_build_dir="/home/amd-edf/edf/builds/$EDF_TARGET"
python3 /opt/edf-scripts/configure.py "$edf_build_dir" || return
cd /opt/edf || return
source ./edf-init-build-env "$edf_build_dir" > "$edf_build_dir/conf/initialization.log" 2>&1 || {
  cat "$edf_build_dir/conf/initialization.log" >&2; return 1;
}
[[ -f conf/bblayers.conf ]] || { echo 'Vendor initialization failed.' >&2; return 1; }
