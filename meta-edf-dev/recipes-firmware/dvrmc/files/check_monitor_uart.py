"""Validate the generated monitor node; never fabricate a node for old hardware."""
import re


def validate(text):
    text = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
    nodes = re.findall(r'(?:\w+:\s*)?[\w-]+@42[cC]00000\s*\{([^{}]*)\};', text)
    if len(nodes) != 1:
        raise ValueError('Matched hardware export must contain one monitor UART Lite at 0x42c00000; regenerate the hardware bundle')
    node = nodes[0]
    def cells(prop):
        match = re.search(r'\b' + re.escape(prop) + r'\s*=\s*<([^>]+)>\s*;', node)
        return match.group(1).split() if match else []
    compat = re.search(r'\bcompatible\s*=([^;]+);', node)
    if not compat or '"xlnx,xps-uartlite-1.00.a"' not in compat.group(1):
        raise ValueError('Monitor UART requires the Linux UART Lite compatible')
    if [int(v, 0) for v in cells('reg')] != [0x42c00000, 0x10000]:
        raise ValueError('Unexpected monitor UART register window')
    if [int(v, 0) for v in cells('current-speed')] != [115200]:
        raise ValueError('Monitor UART hardware must be 115200 baud')
    if not cells('interrupts') or not cells('interrupt-parent'):
        raise ValueError('Monitor UART requires generated IRQ wiring')
    status = re.search(r'\bstatus\s*=\s*"([^"]+)"', node)
    if status and status.group(1) not in ('ok', 'okay'):
        raise ValueError('Monitor UART is disabled')
    # UART Lite is not the PS console. Preserve generated IRQ/clock information.
    if re.search(r'console=ttyUL|stdout-path\s*=\s*"[^";]*(?:42c00000|ttyUL)', text):
        raise ValueError('Monitor UART cannot be a console')
