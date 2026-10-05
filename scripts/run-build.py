#!/usr/bin/env python3
"""Own a single Compose build container, including terminal cancellation."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import uuid

DOCKER = ['docker', '--context', 'orbstack']


def main():
    action, target = sys.argv[1:]
    name = f'edf-dev-{target}-{action}-{uuid.uuid4().hex[:12]}'
    interrupted = 0

    def cancel(signum, frame):
        nonlocal interrupted
        interrupted = interrupted or signum

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, cancel)

    def start(args, **kwargs):
        # Terminal Ctrl+C belongs to this supervisor, not its Docker clients.
        return subprocess.Popen(DOCKER + args, start_new_session=True, **kwargs)

    def cleanup():
        exists = subprocess.run(DOCKER + ['container', 'inspect', name],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        if exists.returncode:
            return True
        subprocess.run(DOCKER + ['stop', '-t', '20', name],
                                 stdout=subprocess.DEVNULL, start_new_session=True)
        removed = subprocess.run(DOCKER + ['rm', '-f', name],
                                 stdout=subprocess.DEVNULL, start_new_session=True)
        return removed.returncode == 0

    logs = waiter = None
    rc = 1
    try:
        # No --rm: retain exit status until docker wait has consumed it.
        # Finish creation before handling cancellation so cleanup cannot race it.
        created = start(['compose', 'run', '-d', '--no-deps', '-T', '--name', name,
                         'shell', '/opt/edf-scripts/export.sh' if action == 'export' else '/opt/edf-scripts/build.sh', action],
                        stdout=subprocess.PIPE)
        _, _ = created.communicate()
        if created.returncode:
            return created.returncode
        if interrupted:
            return 128 + interrupted
        logpath = Path('validation') / f'{target}-{action}.log'
        with logpath.open('wb') as log:
            logs = start(['logs', '--follow', name], stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)

            def copy_output():
                while True:
                    data = os.read(logs.stdout.fileno(), 65536)
                    if not data:
                        break
                    log.write(data)
                    log.flush()
                    try:
                        sys.stdout.buffer.write(data)
                        sys.stdout.buffer.flush()
                    except BrokenPipeError:
                        pass  # Continue saving logs and managing the container.

            reader = threading.Thread(target=copy_output)
            reader.start()
            waiter = start(['wait', name], stdout=subprocess.PIPE)
            while waiter.poll() is None and not interrupted:
                try:
                    waiter.wait(timeout=0.2)
                except subprocess.TimeoutExpired:
                    pass
            if interrupted:
                print('\nStopping this build container (up to 20 seconds)…', file=sys.stderr)
                subprocess.run(DOCKER + ['stop', '-t', '20', name],
                               stdout=subprocess.DEVNULL, start_new_session=True)
                rc = 128 + interrupted
            else:
                value = waiter.communicate()[0].strip()
                rc = int(value) if waiter.returncode == 0 and value.isdigit() else 1
            try:
                logs.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logs.terminate()
                logs.wait()
            reader.join()
    finally:
        if not cleanup():
            print(f'Could not remove {name}; inspect it before retrying.', file=sys.stderr)
            rc = 1
        for child in (logs, waiter):
            if child is not None and child.poll() is None:
                child.terminate()
                child.wait()
    return 128 + interrupted if interrupted else rc


if __name__ == '__main__':
    sys.exit(main())
