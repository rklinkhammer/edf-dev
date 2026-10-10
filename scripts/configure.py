#!/usr/bin/env python3
"""Render generated configuration without invalidating unchanged parse caches."""
import os, pathlib, sys, tempfile
build=pathlib.Path(sys.argv[1]); conf=build/'conf'; conf.mkdir(parents=True,exist_ok=True)
templates=pathlib.Path('/opt/edf/sources/meta-amd-edf/conf/templates/default')
def publish(name,content):
    target=conf/name
    if target.exists() and target.read_text()==content: return
    with tempfile.NamedTemporaryFile(mode='w',dir=conf,delete=False) as f:
        f.write(content); scratch=pathlib.Path(f.name)
    scratch.replace(target)
layers=(templates/'bblayers.conf.sample').read_text().replace('##OEROOT##','/opt/edf/sources/poky')
publish('bblayers.conf',layers+'BBLAYERS += "/project/meta-edf-dev"\n')
local=(templates/'local.conf.sample').read_text()
local+='MACHINE ??= "'+os.environ['BOARD_MACHINE']+'"\nrequire /opt/edf-config/build-policy.inc\ninclude /project/config/targets/'+os.environ['EDF_TARGET']+'.conf\n'
publish('local.conf',local)
