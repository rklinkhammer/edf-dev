"""Opt-in Docker integration tests; no EDF build volumes are mounted."""
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOCKER = ['docker', '--context', 'orbstack']


@unittest.skipUnless(os.environ.get('EDF_DOCKER_TESTS') == '1', 'requires local EDF image and Docker')
class BuildCancellation(unittest.TestCase):
    def test_lifecycle(self):
        with tempfile.TemporaryDirectory(prefix='edf-cancel-test-') as tmp:
            root = Path(tmp)
            (root/'validation').mkdir()
            (root/'scripts').mkdir()
            shutil.copy2(ROOT/'edf', root/'edf')
            shutil.copy2(ROOT/'scripts/run-build.py', root/'scripts/run-build.py')
            worker = root/'worker.sh'
            worker.write_text('''#!/bin/bash
exec 9>/test/lock
flock -n 9 || exit 99
if [[ $1 == check ]]; then echo CHECK; exit 23; fi
echo READY
sleep 600 &
wait
''')
            compose = root/'compose.json'
            compose.write_text(json.dumps({'name': 'edf-cancel-test', 'services': {'shell': {
                'image': 'edf-dev:ubuntu2204-26.06.1', 'platform': 'linux/amd64',
                'init': True, 'entrypoint': ['/bin/bash'],
                'volumes': [f'{worker}:/opt/edf-scripts/build.sh:ro', f'{root}:/test']
            }}}))
            env = {**os.environ, 'COMPOSE_FILE': str(compose)}
            baseline = subprocess.check_output(DOCKER+['ps','-q']).split()
            try:
                for action, cancel_early in [('check', False), ('boot', False), ('boot', True)]:
                    with (root/'output').open('wb') as out:
                        proc = subprocess.Popen([str(root/'edf'), action, 'zc702'],
                                                cwd=root, env=env, stdout=out, stderr=out, start_new_session=True)
                        try:
                            if action == 'boot':
                                if cancel_early:
                                    time.sleep(0.1)
                                else:
                                    deadline = time.monotonic()+30
                                    while b'READY' not in (root/'output').read_bytes():
                                        self.assertIsNone(proc.poll())
                                        self.assertLess(time.monotonic(), deadline)
                                        time.sleep(0.1)
                                os.killpg(proc.pid, signal.SIGINT)
                            code = proc.wait(timeout=45)
                            self.assertEqual(code, 23 if action == 'check' else 130, (root/'output').read_text())
                        finally:
                            if proc.poll() is None:
                                proc.kill(); proc.wait()
                    leftovers = subprocess.check_output(DOCKER+['ps','-aq','--filter','label=com.docker.compose.project=edf-cancel-test']).strip()
                    self.assertFalse(leftovers)
                # A second check acquires the same lock after cancellation.
                result = subprocess.run([str(root/'edf'), 'check', 'zc702'],
                                        cwd=root, env=env, capture_output=True)
                self.assertEqual(result.returncode, 23)
                self.assertEqual(subprocess.check_output(DOCKER+['ps','-q']).split(), baseline)
            finally:
                subprocess.run(DOCKER+['compose','-f',str(compose),'down','--remove-orphans'], capture_output=True)


if __name__ == '__main__':
    unittest.main()
