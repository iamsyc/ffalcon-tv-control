"""The actual source packager must exclude device logs after normal verification."""
from pathlib import Path
import contextlib
import io
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import check_release


class ReleaseTests(unittest.TestCase):
    def test_source_archive_excludes_logs_but_keeps_sources(self):
        with tempfile.TemporaryDirectory(prefix='tv-source-check-') as tmp:
            root = Path(tmp)
            for source in check_release.public_files():
                target = root / source.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True);shutil.copy2(source, target)
            for relative in ['tests/device/wire-click.log', 'tools/session.log']:
                (root / relative).write_text('LOCAL DEVICE SESSION OUTPUT\n')
            result = subprocess.run([sys.executable, 'tools/package.py'], cwd=root,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            with zipfile.ZipFile(root / '.build/ffalcon-tv-control-source.zip') as archive:
                names = archive.namelist()
                self.assertIn('ffalcon-tv-control/tests/device/verify_desktop_click.py', names)
                self.assertIn('ffalcon-tv-control/README.md', names)
                self.assertFalse(any(name.endswith('.log') for name in names), names)

    def test_click_test_writes_log_to_local_device_checks(self):
        with tempfile.TemporaryDirectory(prefix='tv-click-check-') as tmp:
            root = Path(tmp);script = root / 'tests/device/verify_desktop_click.py'
            script.parent.mkdir(parents=True)
            shutil.copy2(ROOT / 'tests/device/verify_desktop_click.py', script)
            reads = 0

            def adb(*args, **kwargs):
                nonlocal reads
                command = args[0]
                if command[1:3] == ['forward', 'tcp:0']:return '12345\n'
                if command[1:] == ['shell', 'cat /data/local/tmp/tv-button-test.xml']:
                    reads += 1
                    texts = ['打开信号源面板'] if reads == 1 else ['应用推荐', '系统应用']
                    return '<hierarchy>' + ''.join(f'<node text="{text}"/>' for text in texts) + '</hierarchy>'
                return ''

            connection = Mock();connection.recv.return_value = b'0' * 65
            with patch.object(sys, 'argv', [str(script), 'fixture-server']), \
                 patch('subprocess.check_output', side_effect=adb), patch('subprocess.Popen'), \
                 patch('socket.create_connection', return_value=connection), patch('time.sleep'), \
                 contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as ended:runpy.run_path(str(script), run_name='__main__')
            self.assertEqual(ended.exception.code, 0)
            self.assertTrue((root / '.local/device-checks/wire-click.log').is_file())
            self.assertFalse((root / 'tests/device/wire-click.log').exists())
