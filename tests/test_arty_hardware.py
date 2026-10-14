import importlib.util
import json
from pathlib import Path
import tempfile
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('arty', ROOT / 'scripts/arty-hardware.py')
arty = importlib.util.module_from_spec(spec)
spec.loader.exec_module(arty)


class Bundle(unittest.TestCase):
    def test_install_and_reject_boot_time_pl(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)/'repo'
            sdt = Path(folder)/'sdt'
            sdt.mkdir()
            (sdt/'system-top.dts').write_text('board = "arty-z7-20";')
            (sdt/'design.bit').write_bytes(b'test bitstream')
            conf = Path(folder)/'conf'
            shutil.copytree(ROOT/'meta-edf-dev/conf', conf)
            arty.install(root, sdt, conf)
            arty.verify(root)
            self.assertEqual((root/'hardware/arty-z7-20/dvrmc.bit').read_bytes(), b'test bitstream')
            base = conf/'dts/arty-z7-20/cortexa9-linux.dts'
            base.write_text(base.read_text() + '\ncontroller@43c00000 {};\n')
            with self.assertRaisesRegex(ValueError, 'base Linux tree'):
                arty.install(root, sdt, conf)

    @unittest.skipUnless(all(shutil.which(t) for t in ('dtc', 'fdtoverlay', 'fdtget')), 'device-tree tools unavailable')
    def test_overlay_resolves_against_linux_base(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            sources = [('base.dtb', 'cortexa9-linux.dts'),
                       ('overlay.dtbo', 'pl-overlay-full/pl.dtso')]
            for dest, source in sources:
                subprocess.run(['dtc', '-@', '-I', 'dts', '-O', 'dtb', '-o', str(out/dest),
                                str(ROOT/'meta-edf-dev/conf/dts/arty-z7-20'/source)],
                               check=True, capture_output=True)
            subprocess.run(['fdtoverlay', '-i', str(out/'base.dtb'), '-o', str(out/'merged.dtb'),
                            str(out/'overlay.dtbo')], check=True, capture_output=True)
            value = subprocess.check_output(['fdtget', '-t', 'x', str(out/'merged.dtb'),
                                             '/axi/controller_axi@43c00000', 'reg'], text=True)
            self.assertEqual(value.strip(), '43c00000 10000')

    def test_manifest_detects_stale_bitstream_and_bsp(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            files = {'hardware/arty-z7-20/dvrmc.bit': b'bitstream',
                     'meta-edf-dev/conf/machine/arty-z7-20.conf': b'machine'}
            for name, content in files.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            record = {'files': {name: arty.sha(root/name) for name in files}}
            (root / arty.MANIFEST).parent.mkdir(parents=True)
            (root / arty.MANIFEST).write_text(json.dumps(record))
            arty.verify(root)
            for name, content in files.items():
                (root/name).write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError, 'Missing or changed'):
                    arty.verify(root)
                (root/name).write_bytes(content)

    def test_checked_in_linux_base_excludes_pl(self):
        base = (ROOT/'meta-edf-dev/conf/dts/arty-z7-20/cortexa9-linux.dts').read_text()
        self.assertIn('"xlnx,zynq-7000"', base)
        self.assertNotIn('43c00000', base)
        self.assertNotIn('firmware-name', base)
        self.assertIn('reg = <0x0 0x20000000>', base)
        overlay = (ROOT/'meta-edf-dev/conf/dts/arty-z7-20/pl-overlay-full/pl.dtso').read_text()
        self.assertIn('firmware-name', overlay)
        self.assertIn('reg = <0x43c00000 0x10000>', overlay)

    def test_boot_excludes_bitstream_and_linux_installs_firmware(self):
        target = (ROOT/'config/targets/arty-z7-20.conf').read_text()
        self.assertIn('BIF_BITSTREAM_ATTR = ""', target)
        self.assertIn('IMAGE_INSTALL:append:pn-edf-linux-disk-image', target)
        self.assertIn('dvrmc-firmware fpga-manager-script', target)
