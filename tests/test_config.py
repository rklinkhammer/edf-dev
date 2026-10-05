import runpy
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
menu = runpy.run_path(str(ROOT/'scripts/rootfs-menu.py'), run_name='test')

class ConfigurationTests(unittest.TestCase):
    def test_rootfs_roundtrip_and_reject_injection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'rootfs.conf'
            values = menu['load'](path)
            values['add_packages'] = 'strace tcpdump'
            menu['save'](path, values)
            self.assertEqual(menu['load'](path), values)
            self.assertIn('IMAGE_INSTALL:append:pn-edf-linux-disk-image = " strace tcpdump"', path.read_text())
            original = path.read_bytes()
            values['add_packages'] = '${@malicious()}'
            with self.assertRaises(ValueError):
                menu['save'](path, values)
            self.assertEqual(path.read_bytes(), original)

    def test_rootfs_preserves_unmanaged_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'rootfs.conf'
            path.write_text('# manually maintained\n')
            with self.assertRaises(ValueError):
                menu['load'](path)

    def test_incremental_kernel_save_keeps_prior_choices(self):
        with tempfile.TemporaryDirectory() as directory:
            build = Path(directory)
            work = build/'work'; work.mkdir()
            (build/'kernel-workdir.txt').write_text(str(work)+'\n')
            folder = build/'conf/edf-kernel'; folder.mkdir(parents=True)
            target = folder/'user.cfg'
            target.write_text('CONFIG_OLD=y\nCONFIG_CHANGED=y\n')
            fragment = work/'fragment.cfg'
            fragment.write_text('# CONFIG_CHANGED is not set\nCONFIG_NEW=m\n')
            subprocess.run([sys.executable, str(ROOT/'scripts/save-kernel.py'), str(build)], check=True, capture_output=True, env={**os.environ, 'LINUX_MACHINE': 'amd-cortexa9thf-neon-common'})
            self.assertEqual(target.read_text(), 'CONFIG_OLD=y\n# CONFIG_CHANGED is not set\nCONFIG_NEW=m\n')
            self.assertIn('SRC_URI:append:pn-linux-xlnx:amd-cortexa9thf-neon-common', (build/'conf/edf-kernel.conf').read_text())
            self.assertNotIn('amd-cortexa53-common', (build/'conf/edf-kernel.conf').read_text())
            before = target.read_bytes()
            fragment.unlink()
            subprocess.run([sys.executable, str(ROOT/'scripts/save-kernel.py'), str(build)], check=True, capture_output=True, env={**os.environ, 'LINUX_MACHINE': 'amd-cortexa9thf-neon-common'})
            self.assertEqual(target.read_bytes(), before)

if __name__ == '__main__':
    unittest.main()
