"""Exercise ADB identity isolation through subprocesses and shipped entry points."""
from pathlib import Path
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runtime'))
import tv_connection as tv


class AdbServerTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.state = self.root / 'state';self.state.mkdir()
        self.foreign = self.root / 'foreign';(self.foreign / '.android').mkdir(parents=True)
        self.foreign_key = self.foreign / '.android/adbkey'
        self.foreign_key.write_text('foreign identity')
        self.key = self.state / 'keys/adbkey';self.key.parent.mkdir()
        self.key.write_text('project identity')
        self.adb = self.root / 'adb'
        self.adb.write_text('#!' + sys.executable + '\n' + '''
from pathlib import Path
import json,os,sys
root=Path(__file__).parent
args=sys.argv[1:]
with (root/'calls.jsonl').open('a') as f:f.write(json.dumps(args)+'\\n')
key=Path(os.environ['HOME'])/'.android/adbkey'
if args==['server-status']:
    if (root/'wrong-status').exists():key=root/'foreign/.android/adbkey'
    print('keystore_path: '+json.dumps(str(key)))
    sys.exit(0)
if args in (['start-server'],['kill-server']):sys.exit(0)
if not key.exists() or key.read_text()!='project identity' or os.environ.get('ADB_VENDOR_KEYS'):
    print('error: device unauthorized.',file=sys.stderr);sys.exit(1)
if args[:1]==['-s']:args=args[2:]
if args[:1]==['connect']:print('connected')
elif args==['get-state']:print('device')
elif args==['shell','id']:print('uid=2000(shell)')
elif args[:1]==['shell']:
    if 'getprop' in args[1]:print('Smart TV Pro')
    elif 'query-activities' in args[1]:print('local.tv.debugentry/.MainActivity')
else:sys.exit('unexpected fixture command: '+repr(args))
''')
        self.adb.chmod(0o755)
        self.c = {'target': '192.0.2.10:5555', 'adb_path': str(self.adb),
                  'adb_key': str(self.key), 'adb_server_port': 5041}
        self.configuration = self.state / 'connection.json'
        self.configuration.write_text(json.dumps(self.c))
        for context in [patch.object(tv, 'CONFIG', self.configuration),
                        patch.dict(os.environ, {'HOME': str(self.foreign),
                                               'TV_CONTROL_HOME': str(self.state),
                                               'ADB_SERVER_SOCKET': 'tcp:localhost:5041',
                                               'ADB_VENDOR_KEYS': str(self.foreign_key)})]:
            context.start();self.addCleanup(context.stop)

    def cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / 'tools/tvctl.py'), *args],
                              capture_output=True, text=True, timeout=10)

    def test_foreign_environment_cannot_supply_the_adb_identity(self):
        result = tv.run_adb(self.c, ['-s', self.c['target'], 'get-state'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'device')
        self.assertEqual(self.foreign_key.read_text(), 'foreign identity')
        self.assertEqual(self.key.read_text(), 'project identity')

    def test_wrong_server_identity_is_rejected_without_command_or_restart(self):
        (self.root / 'wrong-status').touch()
        with self.assertRaisesRegex(RuntimeError, '密钥'):
            tv.run_adb(self.c, ['shell', 'id'])
        calls = [json.loads(line) for line in (self.root / 'calls.jsonl').read_text().splitlines()]
        self.assertEqual(calls, [['server-status']])

    def test_missing_key_does_not_start_adb_or_generate_an_identity(self):
        self.key.unlink()
        with self.assertRaisesRegex(RuntimeError, '密钥'):
            tv.run_adb(self.c, ['devices'])
        self.assertFalse((self.root / 'calls.jsonl').exists())
        self.assertFalse(self.key.exists())

    def test_socket_is_stable_and_changes_with_identity_or_state(self):
        first = tv.adb_env(self.c)['ADB_SERVER_SOCKET']
        self.assertTrue(first.startswith('localfilesystem:'), first)
        self.assertEqual(first, tv.adb_env(dict(self.c))['ADB_SERVER_SOCKET'])
        self.key.write_text('replacement identity')
        self.assertNotEqual(first, tv.adb_env(self.c)['ADB_SERVER_SOCKET'])
        self.key.write_text('project identity')
        with patch.object(tv, 'CONFIG', self.root / 'other/connection.json'):
            self.assertNotEqual(first, tv.adb_env(self.c)['ADB_SERVER_SOCKET'])

    def test_cli_status_shell_and_restart_share_the_project_identity(self):
        for args in [('status',), ('adb', 'shell', 'id'), ('server-restart',)]:
            with self.subTest(args=args):
                result = self.cli(*args)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_cli_passthrough_rejects_a_foreign_server(self):
        (self.root / 'wrong-status').touch()
        result = self.cli('adb', 'shell', 'id')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('密钥', result.stderr)
        calls = [json.loads(line) for line in (self.root / 'calls.jsonl').read_text().splitlines()]
        self.assertEqual(calls, [['server-status']])

    def test_console_backend_uses_the_isolated_identity(self):
        spec = importlib.util.spec_from_file_location('isolated_tv_backend', ROOT / 'macos/backend.py')
        backend = importlib.util.module_from_spec(spec);spec.loader.exec_module(backend)
        result = backend.main('status', [])
        self.assertEqual(result['message'], '已连接 · Smart TV Pro')
        self.assertEqual(result['apps'][0]['package'], 'local.tv.debugentry')

    def test_realtime_launcher_passes_the_same_socket_and_key_to_scrcpy(self):
        bundle = self.root / 'Video.app/Contents'
        binary = bundle / 'MacOS';binary.mkdir(parents=True)
        resources = bundle / 'Resources';resources.mkdir()
        shutil.copy2(ROOT / 'runtime/tv_connection.py', resources / 'tv_connection.py')
        shutil.copy2(ROOT / 'macos/TVControl.py', binary / 'TVControl')
        engine = binary / 'ScrcpyEngine'
        engine.write_text('#!' + sys.executable + '\n' + '''
from pathlib import Path
import json,os
key=Path(os.environ['HOME'])/'.android/adbkey'
Path(__file__).with_name('capture.json').write_text(json.dumps({
    'socket':os.environ['ADB_SERVER_SOCKET'], 'identity':key.read_text(),
    'vendor_keys':os.environ.get('ADB_VENDOR_KEYS')}))
''')
        engine.chmod(0o755)
        result = subprocess.run([sys.executable, str(binary / 'TVControl')],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        capture = json.loads((binary / 'capture.json').read_text())
        self.assertEqual(capture['socket'], tv.adb_env(self.c)['ADB_SERVER_SOCKET'])
        self.assertEqual(capture['identity'], 'project identity')
        self.assertIsNone(capture['vendor_keys'])


if __name__ == '__main__':unittest.main()
