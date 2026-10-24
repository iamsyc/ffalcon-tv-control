#!/usr/bin/env python3
"""Build the actual patched server from a source snapshot whose path has spaces."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from check_release import public_files


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='tv build check ') as tmp:
        project = Path(tmp) / 'TV Tools';project.mkdir()
        for source in public_files():
            target = project / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True);shutil.copy2(source, target)
        cached = ROOT / '.cache/scrcpy-5.0.1.tar.gz'
        if cached.exists():
            (project / '.cache').mkdir();shutil.copy2(cached, project / '.cache' / cached.name)
        subprocess.run([sys.executable, 'tools/build.py', 'server'], cwd=project, check=True)
        with zipfile.ZipFile(project / '.build/server/scrcpy-server') as archive:
            dex = archive.read('classes.dex')
            assert dex.startswith(b'dex\n') and b'TvButtonController' in dex
        print('PASS: real patched server built under a path containing spaces.')
