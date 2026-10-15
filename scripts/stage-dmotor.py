#!/usr/bin/env python3
"""Stage the pinned clean submodule; explicit local override is development-only."""
import os
from pathlib import Path
import subprocess
root = Path(__file__).resolve().parent.parent
source = Path(os.environ.get('EDF_DMOTOR_SOURCE', root/'external/dmotor')).resolve()
if not (source/'software/yocto/stage.py').is_file():
    raise SystemExit('Initialize DMOTOR: git submodule update --init --recursive')
if 'EDF_DMOTOR_SOURCE' not in os.environ:
    head = subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'], text=True).strip()
    entry = subprocess.check_output(['git','-C',str(root),'ls-files','--stage','external/dmotor'], text=True).split()
    dirty = subprocess.check_output(['git','-C',str(source),'status','--porcelain'], text=True).strip()
    if not entry or head != entry[1] or dirty:
        raise SystemExit('DMOTOR must match the clean gitlink; update/stage the submodule pointer or use EDF_DMOTOR_SOURCE explicitly')
subprocess.run(['python3',str(source/'software/yocto/stage.py'),str(root)],check=True)
