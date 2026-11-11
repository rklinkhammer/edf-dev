import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from zybo_linux import prepare
spec = importlib.util.spec_from_file_location('zybo_import_test', ROOT / 'scripts/arty-hardware.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def linux_fixture():
    # Synthetic generated-tree fixture, not hardware acceptance evidence.
    s = (ROOT / 'meta-edf-dev/conf/dts/arty-z7-20/cortexa9-linux.dts').read_text()
    s = s.replace('arty-z7-20', 'zybo-z7-20').replace('reg = <0x0 0x20000000>', 'reg = <0x0 0x40000000>')
    s = re.sub(r'(uart1: serial@e0001000\s*\{.*?status = )"disabled"', r'\1"okay"', s, flags=re.S)
    return s


class Zybo(unittest.TestCase):
    def tearDown(self):
        module.select_target('arty-z7-20')

    def test_linux_console_monitor_separation(self):
        s = prepare(linux_fixture())
        self.assertIn('serial0 = "/axi/serial@e0001000";', s)
        self.assertIn('serial1 = "/axi/serial@e0000000";', s)
        self.assertIn('console=ttyPS0,115200n8', s)
        self.assertEqual(prepare(s), s)

    def test_boot_domain_console(self):
        source = linux_fixture().replace('0x40000000', '0x3ff00000').replace('serial0:115200n8', 'serial0:9600n8')
        result = prepare(source, linux=False)
        self.assertIn('serial0 = "/axi/serial@e0001000";', result)
        self.assertIn('stdout-path = "serial0:115200n8";', result)
        self.assertNotIn('console=ttyPS0', result)
        self.assertEqual(prepare(result, linux=False), result)

    def test_reject_wrong_memory_or_uart(self):
        good = linux_fixture()
        for bad in [good.replace('0x40000000', '0x20000000'),
                    good.replace('serial@e0000000', 'serial@e0002000'),
                    good.replace('uart0: serial@e0000000 {', 'uart0: serial@e0000000 { status = "disabled";')]:
            with self.subTest(bad=bad[:80]), self.assertRaises(ValueError):
                prepare(bad)

    def test_zybo_bundle_isolated_and_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); sdt = root/'sdt'; conf = root/'conf'; dest = root/'repo'
            sdt.mkdir(); (sdt/'system-top.dts').write_text('board = "zybo-z7-20";')
            (sdt/'design.bit').write_bytes(b'fixture only')
            for name in ['machine/zybo-z7-20.conf', 'multiconfig/zybo-z7-20-cortexa9-fsbl.conf',
                         'dts/zybo-z7-20/zybo-z7-20-cortexa9-fsbl.dts']:
                p = conf/name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(linux_fixture() if name.endswith('.dts') else 'fixture\n')
            dts = conf/'dts/zybo-z7-20'; (dts/'cortexa9-linux.dts').write_text(linux_fixture())
            (dts/'pl-overlay-full').mkdir()
            (dts/'pl-overlay-full/pl.dtso').write_text('controller@43c00000 { firmware-name = "design.bit.bin"; };')
            module.select_target('zybo-z7-20'); module.install(dest, sdt, conf); module.verify(dest)
            (sdt/'system-top.dts').write_text('board = "arty-z7-20";')
            with self.assertRaisesRegex(ValueError, 'Expected a zybo-z7-20 SDT'):
                module.install(root/'wrong-board', sdt, conf)
            self.assertFalse((dest/'hardware/arty-z7-20').exists())
            self.assertEqual(json.loads((dest/module.MANIFEST).read_text())['machine'], 'zybo-z7-20')
            record = json.loads((dest/module.MANIFEST).read_text()); record['machine'] = 'arty-z7-20'
            (dest/module.MANIFEST).write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError, 'target mismatch'): module.verify(dest)

    def test_reject_unsupported_target(self):
        module.select_target('zybo-z7-20')
        with self.assertRaises(ValueError): module.select_target('zc702')

    def test_firmware_binding_selects_correct_halt_gpio(self):
        import textwrap
        from types import SimpleNamespace
        recipe = (ROOT/'meta-edf-dev/recipes-firmware/dvrmc/dvrmc-firmware.bb').read_text()
        code = textwrap.dedent(recipe.split('python do_patch:append() {\n')[1].split('\n}')[0])
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            shutil.copy(ROOT/'meta-edf-dev/recipes-firmware/dvrmc/files/check_monitor_uart.py', folder)
            overlay = folder/'dvrmc.dtso'
            text = 'axi_gpio_mc: gpio@41200000 {};\ncontroller@43c00000 { compatible = "xlnx,controller-axi-0.18"; };'
            values = {'WORKDIR':temp, 'EDF_MONITOR_UART':'ps-uart0', 'EDF_HALT_GPIO':'axi_gpio_mc',
                      'EDF_HALT_GPIO_ADDRESS':'41200000', 'EDF_DMOTOR_ACCESS':'production'}
            def fatal(message): raise ValueError(message)
            scope = {'d':SimpleNamespace(getVar=values.get), 'bb':SimpleNamespace(fatal=fatal)}
            overlay.write_text(text); exec(code, scope)
            self.assertIn('halt-gpios = <&axi_gpio_mc 0 0>', overlay.read_text())
            values['EDF_HALT_GPIO'] = 'axi_gpio_3'; overlay.write_text(text)
            with self.assertRaises(ValueError): exec(code, scope)
