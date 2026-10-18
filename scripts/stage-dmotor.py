#!/usr/bin/env python3
"""Stage software from the same resolver used by the FPGA workflow."""
import json
import os
import runpy
import subprocess
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
try:
    source=runpy.run_path(str(root/'scripts/dmotor-source.py'))['resolve']()
    manifest=root/'config/hardware/arty-z7-20.json'
    if os.environ.get('EDF_TARGET')=='arty-z7-20' and manifest.exists():
        expected=json.loads(manifest.read_text()).get('dmotor',{}).get('dmotor_hardware_sha256')
        if expected:
            builder=source/'tools/build.py'
            if not builder.exists() or runpy.run_path(str(builder))['fingerprint']()!=expected:
                raise ValueError('Selected DMOTOR hardware sources differ from the installed bundle; run hardware or select the matching source')
    subprocess.run([sys.executable,str(source/'software/yocto/stage.py'),str(root)],check=True)
except ValueError as e: sys.exit(str(e))
