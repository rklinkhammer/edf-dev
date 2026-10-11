#!/usr/bin/env python3
"""Stream an attached Compose build and own its cancellation and log file."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import uuid

DOCKER = ['docker'] + (['--context', os.environ['EDF_DOCKER_CONTEXT']] if os.environ.get('EDF_DOCKER_CONTEXT') else [])


def main():
    target, *arguments = sys.argv[1:]
    name = f'edf-dev-next-{target}-{uuid.uuid4().hex[:12]}'
    interrupted = 0

    def cancel(signum, frame):
        nonlocal interrupted
        interrupted = interrupted or signum

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, cancel)

    def docker(*args, **kwargs):
        return subprocess.run(DOCKER + list(args), start_new_session=True, **kwargs)

    logdir = Path(os.environ.get('EDF_ARTIFACTS', 'artifacts')) / 'logs' / target
    logdir.mkdir(parents=True, exist_ok=True)
    logpath = logdir / f'{name}.log'
    print(f'Build log: {logpath}', flush=True)
    terminal = sys.stdout.isatty()
    options = ['--no-tty=false' if terminal else '-T', '--interactive=false']
    if terminal:
        term = os.environ.get('TERM', 'xterm')
        size = os.get_terminal_size(sys.stdout.fileno())
        options += ['-e', 'TERM=' + (term if term and term != 'dumb' else 'xterm'),
                    '-e', f'COLUMNS={size.columns or 80}', '-e', f'LINES={size.lines or 24}']

    rc = 1
    with logpath.open('wb') as log:
        # Attach from creation: no lost startup output and no Docker log-driver
        # buffering of BitBake's carriage-return progress updates.
        process = subprocess.Popen(
            DOCKER + ['compose', 'run', '--no-deps', *options, '--name', name,
                      'shell', '/opt/edf-scripts/build.sh', *arguments],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, start_new_session=True)

        def copy_output():
            while True:
                data = os.read(process.stdout.fileno(), 65536)
                if not data:
                    break
                log.write(data)
                log.flush()
                try:
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()
                except BrokenPipeError:
                    pass

        reader = threading.Thread(target=copy_output)
        reader.start()
        stopping = False
        try:
            while process.poll() is None:
                if interrupted:
                    if not stopping:
                        print('\nStopping this build container (up to 20 seconds)…', file=sys.stderr)
                        stopping = True
                    # Creation can still be in flight when Ctrl+C arrives.
                    # Retry until this named container exists or Compose exits.
                    exists = docker('container', 'inspect', name,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    if exists.returncode == 0:
                        docker('stop', '-t', '20', name, stdout=subprocess.DEVNULL)
                try:
                    process.wait(timeout=0.2)
                except subprocess.TimeoutExpired:
                    pass
            rc = process.returncode
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait()
            exists = docker('container', 'inspect', name,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if exists.returncode == 0:
                removed = docker('rm', '-f', name, stdout=subprocess.DEVNULL)
                if removed.returncode:
                    print(f'Could not remove {name}; inspect it before retrying.', file=sys.stderr)
                    rc = 1
            reader.join()
            process.stdout.close()
    return 128 + interrupted if interrupted else rc


if __name__ == '__main__':
    sys.exit(main())
