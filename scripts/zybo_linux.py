"""Prepare Linux and boot-domain UART aliases for the reviewed Zybo MIO layout.
UART1 (MIO48/49) is the USB console; UART0 (MIO14/15) is the monitor.
Never synthesize a missing UART node or relax generated clock/IRQ requirements.
"""
import re


def prepare(text, *, linux=True):
    for address in ('e0000000', 'e0001000'):
        nodes = re.findall(r'\bserial@' + address + r'\s*\{([^{}]*)\};', text)
        if len(nodes) != 1:
            raise ValueError('Zybo needs one generated PS UART at ' + address)
        node = nodes[0]
        if 'xlnx,xuartps' not in node or not re.search(r'\binterrupts\s*=', node) or not re.search(r'\bclocks\s*=', node):
            raise ValueError('Zybo PS UART lacks compatible/clock/IRQ: ' + address)
        status = re.search(r'\bstatus\s*=\s*"([^"]+)"', node)
        if status and status[1] not in ('ok', 'okay'):
            raise ValueError('Zybo PS UART disabled: ' + address)
    if linux:
        memory = re.search(r'\bmemory(?:@\w+)?\s*\{([^{}]*)\}', text)
        reg = re.search(r'\breg\s*=\s*<([^>]+)>', memory[1]) if memory else None
        if not reg or [int(v, 0) for v in reg[1].split()] != [0, 0x40000000]:
            raise ValueError('Zybo Linux memory must describe 1 GiB at address zero')
    # Generated Zynq Linux trees use this bus. Reject changed topology explicitly.
    if not re.search(r'\b(?:axi|amba)\s*\{', text):
        raise ValueError('Unsupported Zybo Linux bus topology')
    bus = re.search(r'\b(axi|amba)\s*\{', text)[1]
    aliases = re.search(r'\baliases\s*\{([^{}]*)\}', text)
    if not aliases:
        raise ValueError('Zybo Linux tree lacks aliases')
    body = re.sub(r'\bserial[01]\s*=\s*[^;]+;', '', aliases[1])
    body = body.rstrip()
    body += f'\n                serial0 = "/{bus}/serial@e0001000";\n                serial1 = "/{bus}/serial@e0000000";\n'
    text = text[:aliases.start(1)] + body + text[aliases.end(1):]
    chosen = re.search(r'\bchosen\s*\{([^{}]*)\}', text)
    if not chosen:
        raise ValueError('Zybo Linux tree lacks chosen')
    body = re.sub(r'\bstdout-path\s*=\s*[^;]+;', '', chosen[1])
    body = body.rstrip()
    body += '\n                stdout-path = "serial0:115200n8";\n'
    if linux:
        bootargs = re.search(r'bootargs\s*=\s*"([^"]*)"\s*;', body)
        args = bootargs[1].split() if bootargs else []
        # Disallow an early console on the monitor and choose the console explicitly.
        args = [a for a in args if not a.startswith(('console=', 'earlycon'))]
        args.append('console=ttyPS0,115200n8')
        prop = 'bootargs = "' + ' '.join(args) + '";'
        body = body[:bootargs.start()] + prop + body[bootargs.end():] if bootargs else body + '\n' + prop
    return text[:chosen.start(1)] + body + text[chosen.end(1):]
