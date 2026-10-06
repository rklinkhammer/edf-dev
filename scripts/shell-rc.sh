# Loaded only by ./edf shell; do not initialize BitBake in the parent shell.
export PATH="/opt/edf-scripts:$PATH"
source /opt/edf-config/targets.sh || return
PS1='[edf:${EDF_TARGET}] \u@\h:\w\$ '
printf '\nTarget: %s\n' "$EDF_TARGET"
edf-build help
printf 'Use exit to leave this shell.\n\n'
