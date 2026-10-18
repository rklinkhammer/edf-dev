"""Portable, checksummed hardware handoff. No symlinks or arbitrary extraction."""
import hashlib
import json
from pathlib import Path
import tarfile

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def paths(root): return sorted(p for p in root.rglob('*') if p.is_file() and p.name!='bundle.json')
def pack(stage, metadata):
    payload=stage/'bundle'
    import shutil
    shutil.copytree(stage/'candidate',payload/'candidate')
    for name in ('dvrmc.xsa','io.rpt','timing.rpt','drc.rpt','workflow.json'):
        if (stage/name).exists(): shutil.copyfile(stage/name,payload/name)
    record={'schema':1,**metadata,'files':{str(p.relative_to(payload)):sha(p) for p in paths(payload)}}
    (payload/'bundle.json').write_text(json.dumps(record,indent=2)+'\n')
    archive=stage/'hardware-bundle.tar.gz'
    with tarfile.open(archive,'w:gz') as out:
        for p in sorted(payload.rglob('*')):
            if p.is_file(): out.add(p,arcname=str(p.relative_to(payload)),recursive=False)
    return archive

def unpack(archive,destination):
    destination.mkdir(parents=True,exist_ok=False)
    seen=set()
    with tarfile.open(archive,'r:gz') as source:
        for item in source:
            name=Path(item.name)
            if not item.isfile() or name.is_absolute() or '..' in name.parts or str(name) in seen:
                raise ValueError('Unsafe or duplicate bundle member: '+item.name)
            seen.add(str(name));target=destination/name;target.parent.mkdir(parents=True,exist_ok=True)
            with source.extractfile(item) as data: target.write_bytes(data.read())
    record=json.loads((destination/'bundle.json').read_text())
    actual={str(p.relative_to(destination)):sha(p) for p in paths(destination)}
    if record.get('schema')!=1 or record.get('files')!=actual: raise ValueError('Hardware bundle checksum mismatch')
    return record
