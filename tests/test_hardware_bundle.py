import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('bundle',ROOT/'scripts/hardware_bundle.py')
bundle=importlib.util.module_from_spec(spec);spec.loader.exec_module(bundle)
class Bundle(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'candidate').mkdir();(root/'candidate/input').write_bytes(b'input')
            (root/'dvrmc.xsa').write_bytes(b'xsa')
            archive=bundle.pack(root,{'dmotor_hardware_sha256':'test'})
            record=bundle.unpack(archive,root/'out')
            self.assertEqual(record['dmotor_hardware_sha256'],'test')
            self.assertEqual((root/'out/candidate/input').read_bytes(),b'input')
    def make(self,root,entries):
        archive=root/'test.tar.gz'
        with tarfile.open(archive,'w:gz') as out:
            for name,value in entries:
                info=tarfile.TarInfo(name);info.size=len(value);out.addfile(info,io.BytesIO(value))
        return archive
    def test_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            archive=self.make(root,[('bundle.json',json.dumps({'schema':1,'files':{'input':'wrong'}}).encode()),('input',b'data')])
            with self.assertRaisesRegex(ValueError,'checksum'):bundle.unpack(archive,root/'out')
    def test_escape_and_duplicate(self):
        for names in (['../escape'],['/escape'],['x','x']):
            with self.subTest(names=names),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);archive=self.make(root,[(n,b'x') for n in names])
                with self.assertRaisesRegex(ValueError,'Unsafe'):bundle.unpack(archive,root/'out')
    def test_link_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);archive=root/'a.tar.gz'
            with tarfile.open(archive,'w:gz') as out:
                info=tarfile.TarInfo('link');info.type=tarfile.SYMTYPE;info.linkname='/etc/passwd';out.addfile(info)
            with self.assertRaisesRegex(ValueError,'Unsafe'):bundle.unpack(archive,root/'out')
