import pathlib, subprocess, tempfile, unittest, os
ROOT=pathlib.Path(__file__).resolve().parents[1]
class LauncherTests(unittest.TestCase):
    def test_invalid_target_never_launches_docker(self):
        result=subprocess.run([str(ROOT/'edf'),'--target','../zc702','check'],capture_output=True,text=True)
        self.assertEqual(result.returncode,2)
        self.assertIn('Unsupported target',result.stderr)
    def test_arty_requires_real_machine_input(self):
        script=(ROOT/'config/targets.sh').read_text().replace('/opt/edf-config',str(ROOT/'config'))
        result=subprocess.run(['bash','-c',script],env={**os.environ,'EDF_TARGET':'arty-z7-20'},capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Arty requires',result.stderr)
