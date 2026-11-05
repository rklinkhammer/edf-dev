import importlib.util
from pathlib import Path
import unittest

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('monitor_check', root / 'meta-edf-dev/recipes-firmware/dvrmc/files/check_monitor_uart.py')
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)
GOOD = '''/plugin/;
&amba { axi_uartlite_0: serial@42c00000 {
compatible = "xlnx,axi-uartlite-2.0", "xlnx,xps-uartlite-1.00.a";
reg = <0x42c00000 0x10000>;
current-speed = <115200>;
interrupt-parent = <&intc>;
interrupts = <0 29 4>;
}; };'''

class MonitorUart(unittest.TestCase):
    def test_generated_node(self):
        check.validate(GOOD)
    def test_stale_or_mismatched_hardware(self):
        for bad in ('', GOOD + GOOD, GOOD.replace('115200', '9600'),
                    GOOD.replace('0x10000', '0x1000'),
                    GOOD.replace('interrupts = <0 29 4>;', ''),
                    GOOD.replace('current-speed', 'status = "disabled"; current-speed'),
                    GOOD + '/* comment */ chosen { bootargs = "console=ttyUL0"; };'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                check.validate(bad)

if __name__ == '__main__': unittest.main()
