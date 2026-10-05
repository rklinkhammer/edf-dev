"""Integration regressions; set QEMUBOOT_TOOL to the release's upstream script."""
import configparser
import os
from pathlib import Path
import runpy
import tempfile
import unittest

merge = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts/prepare-qemu.py'))['merge_configs']

@unittest.skipUnless(os.environ.get('QEMUBOOT_TOOL'), 'requires the upstream EDF qemuboot-tool')
class MergeTests(unittest.TestCase):
    def test_optional_root_and_merge_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory) / 'board.conf'
            image = Path(directory) / 'image.conf'
            image.write_text('[config_bsp]\nimage_name=linux\nimage_link_name=linux\nqb_kernel_root=/dev/mmcblk0p3\nqb_machine=wrong-model\n')
            for extra in ('', 'qb_kernel_root=/dev/wrong\n'):
                with self.subTest(board_root=extra):
                    board.write_text('[config_bsp]\nimage_name=boot\nimage_link_name=boot\nqb_machine=board-model\n' + extra)
                    parsed = configparser.ConfigParser()
                    parsed.read_string(merge(os.environ['QEMUBOOT_TOOL'], board, image))
                    self.assertEqual(parsed['config_bsp']['qb_kernel_root'], '/dev/mmcblk0p3')
                    self.assertEqual(parsed['config_bsp']['image_name'], 'linux')
                    self.assertEqual(parsed['config_bsp']['image_link_name'], 'linux')
                    self.assertEqual(parsed['config_bsp']['qb_machine'], 'board-model')

    def test_upstream_diagnostic_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory) / 'board.conf'
            board.write_text('[config_bsp]\nimage_name=boot\n')
            with self.assertRaisesRegex(RuntimeError, 'does not exist'):
                merge(os.environ['QEMUBOOT_TOOL'], board, Path(directory) / 'missing.conf')

if __name__ == '__main__':
    unittest.main()
