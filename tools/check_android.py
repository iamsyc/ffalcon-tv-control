#!/usr/bin/env python3
"""Host-only checks for helper HTTP, commands, ADB framing and socket cleanup."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'android/helper'


def main():
    with tempfile.TemporaryDirectory(prefix='tv-helper-check-') as tmp:
        names = ['LocalServer', 'ReadProbes', 'AdbProbe', 'AdbBridge', 'VendorAdbCommands']
        suites = ['CoreChecks', 'AdbChecks', 'VendorAdbChecks', 'CommandChecks']
        java = [SOURCE / f'local/tv/debugentry/{name}.java' for name in names]
        java += [SOURCE / f'{name}.java' for name in suites]
        subprocess.run(['javac', '-encoding', 'UTF-8', '-d', tmp, *map(str, java)], check=True)
        for suite in suites:
            print('RUN', suite, flush=True)
            subprocess.run(['java', '-cp', tmp, suite], check=True)
    if not os.environ.get('ANDROID_HOME'):
        raise RuntimeError('socket 生命周期检查需要 ANDROID_HOME 和 android-35。')
    subprocess.run([sys.executable, str(SOURCE / 'tests/run_socket_lifecycle.py')], check=True)


if __name__ == '__main__':
    main()
