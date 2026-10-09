#!/bin/bash
set -euo pipefail
[[ $(id -u) != 0 && $(uname -m) == x86_64 ]]
locale charmap | grep -qi UTF-8
for tool in git git-lfs python3 gcc g++ make gawk flock wget diffstat chrpath socat cpio xz zstd lz4; do
  command -v "$tool" >/dev/null || { echo "Missing build tool: $tool" >&2; exit 1; }
done
python3 /opt/edf-scripts/preflight.py
scratch=$(mktemp -d /home/amd-edf/edf/.compiler-check-XXXXXX)
trap 'rm -rf "$scratch"' EXIT
printf 'int main(void){return 0;}\n' > "$scratch/check.c"
gcc "$scratch/check.c" -o "$scratch/check"
"$scratch/check"
printf 'PASS native compiler, executable build storage and UTF-8 locale\n'
