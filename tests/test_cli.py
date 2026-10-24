"""Run the real CLI with an isolated state directory and a keygen-only fake adb."""
from pathlib import Path
import json
import os
import select
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        adb = self.folder / 'adb'
        adb.write_text('#!' + sys.executable + '\n'
                       'from pathlib import Path\nimport sys\n'
                       'assert sys.argv[1] == "keygen", sys.argv\n'
                       'Path(sys.argv[2]).write_text("test-private-key")\n'
                       'Path(sys.argv[2]+".pub").write_text("QUJDRA== fixture\\n")\n')
        adb.chmod(0o755)
        self.env = {**os.environ, 'TV_CONTROL_HOME': str(self.folder / 'state'),
                    'PATH': str(self.folder)}

    def cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / 'tools/tvctl.py'), *args],
                              env=self.env, capture_output=True, text=True)

    def test_init_is_local_only_and_does_not_overwrite_identity(self):
        result = self.cli('init', '--host', '192.0.2.10', '--port', '34961')
        self.assertEqual(result.returncode, 0, result.stderr)
        config_file = self.folder / 'state/connection.json'
        c = json.loads(config_file.read_text())
        self.assertEqual(c['target'], '192.0.2.10:34961')
        self.assertNotIn('adb_server_port', c)
        self.assertEqual(Path(c['adb_key']).stat().st_mode & 0o777, 0o600)
        before = config_file.read_bytes()
        result = self.cli('init', '--host', '192.0.2.20', '--port', '5555')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(config_file.read_bytes(), before)

    def test_invalid_port_does_not_create_state(self):
        result = self.cli('init', '--host', '192.0.2.10', '--port', '70000')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.folder / 'state').exists())

    def test_pair_prompt_is_visible_before_entering_code(self):
        result = self.cli('init', '--host', '192.0.2.10', '--port', '34961')
        self.assertEqual(result.returncode, 0, result.stderr)
        (self.folder / 'adb').write_text(
            '#!' + sys.executable + '\nimport sys,os,json\nfrom pathlib import Path\n'
            'if sys.argv[1:] == ["server-status"]:\n'
            ' print("keystore_path: "+json.dumps(str(Path(os.environ["HOME"])/".android/adbkey")))\n'
            ' sys.exit(0)\n'
            'print("Enter pairing code: ", end="", flush=True)\n'
            'code = input()\n'
            'print("PAIR ACCEPTED" if code == "123456" else "BAD CODE")\n')
        child = subprocess.Popen(
            [sys.executable, str(ROOT / 'tools/tvctl.py'), 'adb', 'pair', '192.0.2.10:37123'],
            env=self.env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            ready = select.select([child.stdout], [], [], 3)[0]
            prompt = os.read(child.stdout.fileno(), 1024) if ready else b''
            output, errors = child.communicate(b'123456\n', timeout=3)
        finally:
            if child.poll() is None:
                child.kill();child.communicate()
        self.assertIn(b'Enter pairing code:', prompt)
        self.assertIn(b'PAIR ACCEPTED', output)
        self.assertEqual(child.returncode, 0, errors)
