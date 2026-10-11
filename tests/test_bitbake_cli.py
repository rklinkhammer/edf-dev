"""Exercise the real launcher/dispatcher with isolated Docker and BitBake probes."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Launcher(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ('bin', 'scripts', 'config/targets', 'artifacts'):
            (self.root / name).mkdir(parents=True)
        (self.root / 'edf').write_text((ROOT / 'edf').read_text())
        (self.root / 'config/targets/zc702.sh').touch()
        (self.root / 'scripts/host-config.py').write_text("import os; print(os.path.join(os.getcwd(), 'artifacts'))\n")
        (self.root / 'scripts/run-build.py').write_text(
            "import json,os,sys; print(json.dumps({'args':sys.argv[1:],'machine':os.environ['EDF_MACHINE'],"
            "'context':os.environ.get('EDF_DOCKER_CONTEXT')})); sys.exit(int(os.environ.get('PROBE_EXIT','0')))\n")
        self.calls = self.root / 'calls'
        docker = self.root / 'bin/docker'
        docker.write_text('#!/usr/bin/env python3\nimport json,os,sys\n'
                          "with open(os.environ['CALLS'],'a') as f: f.write(json.dumps(sys.argv[1:])+'\\n')\n")
        docker.chmod(0o755)
        uname = self.root / 'bin/uname'
        uname.write_text('#!/bin/sh\nprintf "%s\\n" "$TEST_OS"\n')
        uname.chmod(0o755)
        self.env = {k:v for k,v in os.environ.items() if not k.startswith(('EDF_', 'DOCKER_'))}
        self.env.update(PATH=str(self.root/'bin')+':'+os.environ['PATH'], CALLS=str(self.calls), TEST_OS='Linux')

    def run_edf(self, args, **env):
        result = subprocess.run(['bash', str(self.root/'edf'), *args], env={**self.env, **env},
                                capture_output=True, text=True)
        return result

    def test_default_is_direct_bitbake(self):
        result = self.run_edf([])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['args'], ['zc702', 'bitbake'])

    def test_argument_boundaries_and_status(self):
        args = ['bitbake', '-R', 'path with spaces.conf', '-c', 'compile', 'linux-xlnx']
        result = self.run_edf(['--machine', 'board', *args], PROBE_EXIT='7')
        self.assertEqual(result.returncode, 7)
        payload = json.loads(result.stdout)
        self.assertEqual(payload['args'], ['zc702', *args])
        self.assertEqual(payload['machine'], 'board')

    def test_context_precedence_and_macos_default(self):
        for env, options, context in [
            ({'TEST_OS':'Darwin'}, [], 'orbstack'),
            ({'TEST_OS':'Darwin','DOCKER_CONTEXT':'remote'}, [], None),
            ({'TEST_OS':'Darwin','DOCKER_HOST':'unix:///tmp/docker.sock'}, [], None),
            ({'TEST_OS':'Darwin','EDF_DOCKER_CONTEXT':''}, [], ''),
            ({'EDF_DOCKER_CONTEXT':'env-context'}, ['--context','cli-context'], 'cli-context'),
            ({}, [], None),
        ]:
            with self.subTest(env=env, options=options):
                self.calls.write_text('')
                result = self.run_edf([*options,'bitbake','--help'], **env)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)['context'], context)
                command = json.loads(self.calls.read_text().splitlines()[0])
                expected = ['--context',context] if context else []
                self.assertEqual(command, expected+['compose','up','-d','--build','--wait','hashserv'])

    def test_aliases_and_escape(self):
        for args, forwarded in [(['image'], ['image']), (['sdk'], ['sdk']),
                                (['--','image'], ['bitbake','image']),
                                (['-n','edf-linux-disk-image'], ['-n','edf-linux-disk-image'])]:
            with self.subTest(args=args):
                result = self.run_edf(args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)['args'], ['zc702', *forwarded])

    def test_invalid_selector_does_not_launch_docker(self):
        for args in (['--machine','../bad'], ['--target'], ['--context']):
            result = self.run_edf(args)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(self.calls.exists())


class Dispatcher(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ('scripts', 'config', 'bin', 'state'):
            (self.root/name).mkdir()
        script = (ROOT/'scripts/build.sh').read_text()
        for old, new in [('/home/amd-edf/edf', str(self.root/'state')),
                         ('/opt/edf-scripts',str(self.root/'scripts')),
                         ('/opt/edf-config',str(self.root/'config'))]:
            script = script.replace(old, new)
        (self.root/'build.sh').write_text(script)
        (self.root/'config/targets.sh').write_text('export BOARD_MACHINE=test-board LINUX_MACHINE=test-linux\nexport BOOT_RECIPE=test-boot IMAGE_RECIPE=test-image\n')
        (self.root/'scripts/yocto-env.sh').write_text('export BUILDDIR="$PWD"\n')
        validate = self.root/'scripts/validate.sh'
        validate.write_text('#!/bin/sh\nexit 0\n'); validate.chmod(0o755)
        bitbake = self.root/'bin/bitbake'
        bitbake.write_text('#!/usr/bin/env python3\nimport json,os,sys\n'
                          "print(json.dumps({'machine':os.environ['MACHINE'],'args':sys.argv[1:]}))\n"
                          "sys.exit(int(os.environ.get('PROBE_EXIT','0')))\n")
        bitbake.chmod(0o755)

    def run_build(self, args, machine='linux', exit_code='0'):
        result = subprocess.run(['/bin/bash',str(self.root/'build.sh'),*args], capture_output=True,text=True,
                                env={**os.environ,'EDF_TARGET':'zc702','EDF_MACHINE':machine,
                                     'PATH':str(self.root/'bin')+':'+os.environ['PATH'], 'PROBE_EXIT':exit_code})
        return result, [json.loads(line) for line in result.stdout.splitlines()]

    def test_direct_machine_and_arguments(self):
        for selection, expected in [('linux','test-linux'), ('board','test-board'), ('custom-machine','custom-machine')]:
            result, calls = self.run_build(['bitbake','-n','-R','a file.conf','recipe'],selection)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(calls,[{'machine':expected,'args':['-n','-R','a file.conf','recipe']}])

    def test_default_and_alias_escape(self):
        for args, expected in [([],['test-image']), (['bitbake'],['test-image']),
                               (['bitbake','image'],['image']), (['-e'],['-e'])]:
            result,calls = self.run_build(args)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(calls,[{'machine':'test-linux','args':expected}])

    def test_convenience_mappings_and_failure(self):
        result,calls = self.run_build(['image'])
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(calls,[{'machine':'test-board','args':['test-boot']},
                                {'machine':'test-linux','args':['test-image']}])
        result,calls = self.run_build(['image'],exit_code='9')
        self.assertEqual(result.returncode,9)
        self.assertEqual(len(calls),1)
        result,calls = self.run_build(['sdk'])
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(calls[0]['args'],['test-image','-c','populate_sdk'])

    def test_shell_inherits_selected_machine(self):
        shell = self.root/'bin/bash'
        shell.write_text('#!/usr/bin/env python3\nimport os,json; print(json.dumps({"machine":os.environ["MACHINE"]}))\n')
        shell.chmod(0o755)
        # The dispatcher's informational line is not part of the shell probe.
        result = subprocess.run(['/bin/bash',str(self.root/'build.sh'),'shell'],capture_output=True,text=True,
                                env={**os.environ,'EDF_TARGET':'zc702','EDF_MACHINE':'board',
                                     'PATH':str(self.root/'bin')+':'+os.environ['PATH']})
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout.splitlines()[-1]),{'machine':'test-board'})
