"""First-load wrapper tests with isolated sysfs/firmware and a fake fpgautil."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'meta-edf-dev/recipes-firmware/dvrmc/files/dmotor-load-fpga'

class LoadFpga(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.fw = self.root / 'firmware with spaces'
        self.fw.mkdir()
        for name in ('dvrmc-firmware.bin', 'dvrmc-firmware.dtbo', 'hardware-inputs.json'):
            (self.fw / name).write_text('fixture')
        self.state = self.root / 'state'
        self.state.write_text('unknown\n')
        self.overlays = self.root / 'overlays'
        self.overlays.mkdir()
        self.marker = self.root / 'called'
        text = SCRIPT.read_text()
        for original, replacement in {
            '/sys/class/fpga_manager/fpga0/state': str(self.state),
            '/sys/kernel/config/device-tree/overlays': str(self.overlays),
            '/run/dmotor-load-fpga.lock': str(self.root / 'lock'),
            '/dev/dmotor0': str(self.root / 'device'),
        }.items():
            text = text.replace(original, replacement)
        self.script = self.root / 'load'
        self.script.write_text(text)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        (self.bin / 'id').write_text('#!/bin/sh\necho "${TEST_UID:-0}"\n')
        (self.bin / 'fpgautil').write_text('''#!/bin/sh
printf '%s\\n' "$@" > "$TEST_MARKER"
[ "${TEST_FAIL:-0}" = 0 ] || exit 1
printf '%s\\n' "${TEST_STATE:-operating}" > "$TEST_STATE_FILE"
''')
        for p in self.bin.iterdir():
            p.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.bin)+':'+os.environ['PATH'],
                        TEST_MARKER=str(self.marker), TEST_STATE_FILE=str(self.state))

    def run_script(self, *args, **env):
        return subprocess.run(['sh', str(self.script), '--firmware-dir', str(self.fw), *args],
                              env=dict(self.env, **env), text=True, capture_output=True)

    def test_load_and_arguments(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.marker.read_text().splitlines(),
                         ['-b', str(self.fw/'dvrmc-firmware.bin'), '-o', str(self.fw/'dvrmc-firmware.dtbo')])
        self.assertFalse((self.root/'lock').exists())

    def test_dry_run_no_programming(self):
        self.assertEqual(self.run_script('--dry-run', TEST_UID='1000').returncode, 0)
        self.assertFalse(self.marker.exists())

    def test_missing_pair(self):
        (self.fw/'dvrmc-firmware.dtbo').unlink()
        self.assertNotEqual(self.run_script().returncode, 0)
        self.assertFalse(self.marker.exists())

    def test_preexisting_state(self):
        for kind in ('operating', 'overlay', 'device', 'lock'):
            with self.subTest(kind=kind):
                path = None
                if kind == 'operating': self.state.write_text('operating\n')
                elif kind == 'overlay': path = self.overlays/'full'; path.mkdir()
                else: path = self.root/kind; path.touch()
                self.assertNotEqual(self.run_script().returncode, 0)
                self.assertFalse(self.marker.exists())
                if path:
                    if path.is_dir(): path.rmdir()
                    else: path.unlink()
                self.state.write_text('unknown\n')

    def test_failure_propagates(self):
        self.assertNotEqual(self.run_script(TEST_FAIL='1').returncode, 0)
        self.assertFalse((self.root/'lock').exists())
        self.assertNotEqual(self.run_script(TEST_STATE='error').returncode, 0)

    def test_nonroot(self):
        self.assertNotEqual(self.run_script(TEST_UID='1000').returncode, 0)
        self.assertFalse(self.marker.exists())

if __name__ == '__main__': unittest.main()
