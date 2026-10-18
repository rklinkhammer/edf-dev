#!/usr/bin/env python3
"""Resolve one DMOTOR checkout for both hardware and software."""
import os
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
def resolve():
    source=Path(os.environ.get('EDF_DMOTOR_SOURCE',ROOT/'external/dmotor')).expanduser().resolve()
    if not (source/'software/yocto/stage.py').is_file():
        raise ValueError('Initialize external/dmotor or set EDF_DMOTOR_SOURCE to the development checkout')
    if 'EDF_DMOTOR_SOURCE' not in os.environ:
        head=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
        entry=subprocess.check_output(['git','-C',str(ROOT),'ls-files','--stage','external/dmotor'],text=True).split()
        dirty=subprocess.check_output(['git','-C',str(source),'status','--porcelain'],text=True).strip()
        if not entry or head!=entry[1] or dirty:
            raise ValueError('DMOTOR must match the clean gitlink; update/stage the pin or set EDF_DMOTOR_SOURCE explicitly')
    return source
if __name__=='__main__':
    try: print(resolve())
    except ValueError as e: raise SystemExit(str(e))
