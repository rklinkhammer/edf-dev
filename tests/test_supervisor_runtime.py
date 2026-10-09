"""Opt-in real Docker cancellation/exit-status regression."""
import os, pathlib, subprocess, tempfile, signal, unittest, uuid
ROOT=pathlib.Path(__file__).resolve().parents[1]
@unittest.skipUnless(os.environ.get('EDF_RUNTIME_TEST'),'requires built container and Docker')
class Supervisor(unittest.TestCase):
    def test_cancel_and_release_then_failure_status(self):
        with tempfile.TemporaryDirectory() as directory:
            project='edf-next-supervisor-test-'+uuid.uuid4().hex[:8]
            work=pathlib.Path(directory)
            script=work/'build.sh'
            script.write_text('#!/bin/bash\nexec 9>/home/amd-edf/edf/probe.lock\nflock -n 9 || exit 99\nif [[ $1 == fail ]]; then exit 7; fi\necho READY\nexec sleep 120\n')
            script.chmod(0o755)
            override=work/'override.yaml'
            override.write_text('services:\n  shell:\n    volumes:\n      - '+str(script)+':/opt/edf-scripts/build.sh:ro\n')
            env={**os.environ,'HOST_UID':str(os.getuid()),'HOST_GID':str(os.getgid()),'HOST_GROUPS':','.join(map(str,os.getgroups())), 'COMPOSE_FILE':str(ROOT/'compose.yaml')+':'+str(override),'COMPOSE_PROJECT_NAME':project,'EDF_ARTIFACTS':str(work),'EDF_DOCKER_CONTEXT':os.environ.get('EDF_DOCKER_CONTEXT','')}
            docker=['docker']+(['--context',env['EDF_DOCKER_CONTEXT']] if env['EDF_DOCKER_CONTEXT'] else [])
            p=subprocess.Popen(['python3',str(ROOT/'scripts/run-build.py'),'zc702','wait'],cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
            output=[]
            try:
                while True:
                    line=p.stdout.readline(); output.append(line)
                    if not line: self.fail('Probe failed: '+''.join(output))
                    if line.strip()=='READY': break
                p.send_signal(signal.SIGINT)
                tail,_=p.communicate(timeout=40); output.append(tail)
                self.assertEqual(p.returncode,130,''.join(output))
                failure=subprocess.run(['python3',str(ROOT/'scripts/run-build.py'),'zc702','fail'],cwd=ROOT,env=env,capture_output=True,text=True,timeout=40)
                self.assertEqual(failure.returncode,7,failure.stdout+failure.stderr)
                logs=list((work/'logs/zc702').glob('*.log'))
                self.assertTrue(any('READY' in log.read_text() for log in logs))
                docker=['docker']+(['--context',env['EDF_DOCKER_CONTEXT']] if env['EDF_DOCKER_CONTEXT'] else [])
                remaining=subprocess.check_output(docker+['ps','-aq','--filter','label=com.docker.compose.project='+project],text=True)
                self.assertFalse(remaining.strip(),remaining)
            finally:
                if p.poll() is None: p.kill();p.wait()
                subprocess.run(docker+['compose','down','--volumes'],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
