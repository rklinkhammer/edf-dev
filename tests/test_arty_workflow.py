import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('workflow',ROOT/'scripts/arty-build.py')
workflow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workflow)

class Publish(unittest.TestCase):
    def fixture(self, root):
        candidate = root/'candidate'; destination = root/'repo'
        name = Path('hardware/arty-z7-20/dvrmc.bit')
        for folder,content in [(candidate,b'new'),(destination,b'old')]:
            (folder/name).parent.mkdir(parents=True)
            (folder/name).write_bytes(content)
        manifest = candidate/workflow.importer.MANIFEST
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({'files':{str(name):workflow.importer.sha(candidate/name)}}))
        return candidate,destination,name

    def test_install_and_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);candidate,destination,name=self.fixture(root)
            workflow.publish(candidate,destination,root/'backup')
            self.assertEqual((destination/name).read_bytes(),b'new')
            self.assertEqual((root/'backup'/name).read_bytes(),b'old')
            workflow.importer.verify(destination)

    def test_rollback_on_verification_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);candidate,destination,name=self.fixture(root)
            with patch.object(workflow.importer,'verify',side_effect=ValueError('failure')):
                with self.assertRaises(ValueError):
                    workflow.publish(candidate,destination,root/'backup')
            self.assertEqual((destination/name).read_bytes(),b'old')
            self.assertFalse((destination/workflow.importer.MANIFEST).exists())

    def test_read_only_replacement_and_rollback(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);candidate,destination,name=self.fixture(root)
            (destination/name).chmod(0o444)
            (candidate/name).chmod(0o444)
            with patch.object(workflow.importer,'verify',side_effect=ValueError('failure')):
                with self.assertRaises(ValueError):
                    workflow.publish(candidate,destination,root/'backup')
            self.assertEqual((destination/name).read_bytes(),b'old')
            workflow.publish(candidate,destination,root/'backup2')
            self.assertEqual((destination/name).read_bytes(),b'new')

    def test_reject_path_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);candidate,destination,_=self.fixture(root)
            (candidate/workflow.importer.MANIFEST).write_text(json.dumps({'files':{'../escape':'bad'}}))
            with self.assertRaises(ValueError):
                workflow.publish(candidate,destination,root/'backup')
            self.assertFalse((root/'backup').exists())

class Lock(unittest.TestCase):
    def test_exclusive_conflict_and_shared_coexistence(self):
        import fcntl
        import shutil
        import subprocess
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'scripts').mkdir()
            script=root/'scripts/hardware-lock.py'
            shutil.copy2(ROOT/'scripts/hardware-lock.py',script)
            target=root/'edf';target.write_text('exit 0\n')
            with (root/'.edf-hardware.lock').open('a') as lock:
                fcntl.flock(lock,fcntl.LOCK_SH)
                result=subprocess.run(['python3',str(script),str(target),'hardware'],capture_output=True)
                self.assertNotEqual(result.returncode,0)
                result=subprocess.run(['python3',str(script),str(target),'bitbake'],capture_output=True)
                self.assertEqual(result.returncode,0,result.stderr)
