"""Exercise install boundaries with isolated files and simulated ADB/tool processes."""
from pathlib import Path
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runtime'))


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


backend = load('tv_backend_checks', 'macos/backend.py')
build = load('tv_build_checks', 'tools/build.py')


class ApkInstallTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.apk = Path(tmp.name) / 'fixture.apk';self.apk.write_bytes(b'fixture')

    def test_push_failure_or_timeout_still_attempts_cleanup(self):
        for failure in [RuntimeError('upload interrupted'), subprocess.TimeoutExpired('adb push', 300)]:
            with self.subTest(error=type(failure).__name__), \
                 patch.object(backend, 'adb', side_effect=failure) as adb, \
                 patch.object(backend, 'shell', return_value='') as shell:
                with self.assertRaises(type(failure)):
                    backend.main('install', [str(self.apk)])
                remote = adb.call_args.args[0][-1]
                shell.assert_called_once_with('rm', '-f', remote)

    def test_pm_install_failure_still_cleans_uploaded_apk(self):
        with patch.object(backend, 'adb', return_value='') as adb, \
             patch.object(backend, 'shell', side_effect=['Failure [INSTALL_FAILED_TEST]', '']) as shell:
            with self.assertRaisesRegex(RuntimeError, 'INSTALL_FAILED_TEST'):
                backend.main('install', [str(self.apk)])
            remote = adb.call_args.args[0][-1]
            self.assertEqual(shell.call_args_list[-1].args, ('rm', '-f', remote))

    def test_success_installs_cleans_and_refreshes_apps(self):
        with patch.object(backend, 'adb', return_value='') as adb, \
             patch.object(backend, 'shell', side_effect=['Success', '']) as shell, \
             patch.object(backend, 'apps', return_value=[]):
            result = backend.main('install', [str(self.apk)])
            remote = adb.call_args.args[0][-1]
            self.assertEqual(shell.call_args_list[0].args, ('pm', 'install', '-r', remote))
            self.assertEqual(shell.call_args_list[1].args, ('rm', '-f', remote))
            self.assertIn('安装成功', result['message'])


class MacInstallTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.home = self.folder / 'user';self.home.mkdir()
        self.build_dir = self.folder / '.build'
        (self.build_dir / 'server').mkdir(parents=True)
        (self.build_dir / 'server/scrcpy-server').write_bytes(b'test-server')
        self.client = self.folder / 'scrcpy';self.client.write_bytes(b'test-client')
        contexts = [patch.object(build.sys, 'platform', 'darwin'),
                    patch.object(build, 'BUILD', self.build_dir),
                    patch.object(build.Path, 'home', return_value=self.home),
                    patch.object(build.shutil, 'which', return_value=str(self.client)),
                    patch.object(build.subprocess, 'check_output', return_value='scrcpy 5.0.1\n'),
                    patch.object(build, 'run', side_effect=self.fake_run)]
        for context in contexts:
            context.start();self.addCleanup(context.stop)

    def fake_run(self, args, **kwargs):
        if args[0] == 'iconutil':Path(args[-1]).write_bytes(b'test-icon')

    def test_second_destination_conflict_prevents_first_install(self):
        existing = self.home / 'Applications/电视控制台.app'
        existing.mkdir(parents=True);(existing / 'owner-file').write_text('preserve')
        with self.assertRaisesRegex(RuntimeError, '已存在'):
            build.macos(install=True)
        self.assertFalse((self.home / 'Applications/客厅电视.app').exists())
        self.assertEqual((existing / 'owner-file').read_text(), 'preserve')

    def test_fresh_install_copies_both_apps(self):
        build.macos(install=True)
        for name in ['客厅电视', '电视控制台']:
            resources = self.home / f'Applications/{name}.app/Contents/Resources'
            self.assertTrue((resources / 'tv_connection.py').is_file())
        self.assertTrue((self.home / 'Applications/电视控制台.app/Contents/Resources/backend.py').is_file())
        self.assertEqual((resources / 'TVConsole.icns').read_bytes(), b'test-icon')

    def test_rebuild_replaces_read_only_client(self):
        self.client.chmod(0o555)
        build.macos()
        self.client.chmod(0o755);self.client.write_bytes(b'updated-client');self.client.chmod(0o555)
        build.macos()
        engine = self.build_dir / 'apps/客厅电视.app/Contents/MacOS/ScrcpyEngine'
        self.assertEqual(engine.read_bytes(), b'updated-client')
        self.assertEqual(self.client.stat().st_mode & 0o777, 0o555)
