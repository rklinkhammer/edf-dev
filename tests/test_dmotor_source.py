import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('dmotor_source',ROOT/'scripts/dmotor-source.py')
source=importlib.util.module_from_spec(spec);spec.loader.exec_module(source)
class Source(unittest.TestCase):
    def fixture(self,root):
        checkout=root/'external/dmotor';(checkout/'software/yocto').mkdir(parents=True)
        (checkout/'software/yocto/stage.py').write_text('')
        return checkout
    def test_one_explicit_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            checkout=self.fixture(Path(tmp))
            with patch.dict(os.environ,{'EDF_DMOTOR_SOURCE':str(checkout)}),patch.object(source.subprocess,'check_output') as git:
                self.assertEqual(source.resolve(),checkout)
                git.assert_not_called()
    def test_pin_and_dirty_rejection(self):
        for head,dirty,accepted in [('abc','',True),('other','',False),('abc',' M file',False)]:
            with self.subTest(head=head,dirty=dirty),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);checkout=self.fixture(root)
                with patch.dict(os.environ,{},clear=True),patch.object(source,'ROOT',root),patch.object(source.subprocess,'check_output',side_effect=[head,'160000 abc 0 external/dmotor',dirty]):
                    if accepted:self.assertEqual(source.resolve(),checkout)
                    else:
                        with self.assertRaises(ValueError):source.resolve()
    def test_software_staging_refuses_hardware_mismatch(self):
        import json
        import shutil
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'scripts').mkdir();(root/'config/hardware').mkdir(parents=True)
            checkout=self.fixture(root);(checkout/'tools').mkdir()
            (checkout/'tools/build.py').write_text("def fingerprint(): return 'actual'\n")
            for name in ('stage-dmotor.py','dmotor-source.py'):shutil.copyfile(ROOT/'scripts'/name,root/'scripts'/name)
            (root/'config/hardware/arty-z7-20.json').write_text(json.dumps({'dmotor':{'dmotor_hardware_sha256':'different'}}))
            result=subprocess.run(['python3',str(root/'scripts/stage-dmotor.py')],env={**os.environ,'EDF_DMOTOR_SOURCE':str(checkout),'EDF_TARGET':'arty-z7-20'},capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('differ from the installed bundle',result.stderr)
