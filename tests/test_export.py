import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('edf_export', Path(__file__).resolve().parents[1]/'scripts/export.py')
export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export)

class ExportInputs(unittest.TestCase):
    def test_missing_outputs_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, 'Complete firmware and Linux'):
                export.required(Path(tmp)/'missing.wic')

    def test_mismatched_machine_rejected_before_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            build=Path(tmp)
            deploy=build/'tmp/deploy/images'
            for machine, name, actual in [('board','BOOT-board.qemuboot.conf','wrong-board'),
                                         ('linux','edf-linux-disk-image-linux.rootfs.qemuboot.conf','linux')]:
                folder=deploy/machine;folder.mkdir(parents=True)
                (folder/name).write_text('[config_bsp]\nmachine = '+actual+'\n')
            with patch.dict('os.environ', EDF_TARGET='test', BOARD_MACHINE='board', LINUX_MACHINE='linux'):
                with self.assertRaisesRegex(RuntimeError,'machine mismatch'):
                    export.main(build)

if __name__ == '__main__': unittest.main()
