#!/usr/bin/env python3
import os, pathlib, tempfile, fcntl, subprocess
for base in ('/project','/opt/edf-scripts','/opt/edf-config','/opt/edf'):
    if os.access(base,os.W_OK): raise SystemExit(f'Expected read-only build input: {base}')
root = pathlib.Path('/home/amd-edf/edf')
kind = subprocess.check_output(['stat','-f','-c','%T',str(root)],text=True).strip()
if kind not in ('ext2/ext3','xfs','btrfs','overlayfs'):
    raise SystemExit(f'Build storage must be local Linux storage, found {kind}')
for base in (root, root/'downloads', root/'sstate-cache', pathlib.Path('/artifacts')):
    with tempfile.TemporaryDirectory(prefix='.edf-preflight-',dir=base) as directory:
        p=pathlib.Path(directory)
        (p/'case').write_text('lower'); (p/'CASE').write_text('upper')
        assert (p/'case').read_text() == 'lower', f'Case-insensitive storage: {base}'
        (p/'link').symlink_to('case'); assert (p/'link').read_text() == 'lower'
        with (p/'lock').open('w') as f: fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
    print(f'PASS storage: {base}')
import sys
sys.path.insert(0,'/opt/edf/sources/poky/bitbake/lib')
import hashserv
c=hashserv.create_client('unix:///hashserv/hashserv.sock'); c.get_stats(); c.close()
print(f'PASS hashserv; UID/GID {os.getuid()}:{os.getgid()}; groups {os.getgroups()}')
