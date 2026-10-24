#!/usr/bin/env python3
"""Check the explicit public source set, never local build/runtime state."""
from pathlib import Path
import re
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
FILES = ['README.md', 'AGENTS.md', 'CONTRIBUTING.md', 'LICENSE', 'NOTICE',
         '.gitignore', 'pyproject.toml', 'versions.json']
DIRECTORIES = ['android', 'macos', 'runtime', 'tools', 'patches', 'tests',
               'docs', 'evidence', 'licenses', '.github']
PUBLIC_IMAGES = {'docs/images/console.png', 'docs/images/realtime.png'}


def public_files():
    paths = [ROOT / item for item in FILES]
    for name in DIRECTORIES:
        paths.extend(p for p in (ROOT / name).rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts and p.suffix not in {'.pyc', '.log'})
    return sorted(paths)


def check():
    errors = []
    patterns = [
        ('private key', r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
        ('personal macOS path', r'[/]Users[/][^/\s]+/'),
        ('private network address', r'\b192\.168\.\d{1,3}\.\d{1,3}\b'),
        ('ADB public key identity', r'(?m)^[A-Za-z0-9+/]{600,}={0,2}\s'),
    ]
    for path in public_files():
        relative = path.relative_to(ROOT)
        if path.is_symlink():
            errors.append(f'{relative}: public files must be ordinary files');continue
        if relative.as_posix() in PUBLIC_IMAGES:
            if not path.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'):
                errors.append(f'{relative}: expected PNG screenshot')
            continue
        if path.suffix in {'.apk', '.keystore', '.jks', '.zip', '.png', '.jpg', '.dex', '.class'}:
            errors.append(f'{relative}: unexpected public binary');continue
        try:
            data = path.read_text()
        except (UnicodeError, OSError) as error:
            errors.append(f'{relative}: {error}');continue
        for label, pattern in patterns:
            if re.search(pattern, data):errors.append(f'{relative}: {label}')
        if path.suffix == '.md':
            for target in re.findall(r'\[[^\]]*\]\(([^)\s]+)\)', data):
                if re.match(r'^[\w+.-]+:', target) or target.startswith('#'):continue
                local = unquote(target.split('#', 1)[0])
                if not (path.parent / local).exists():
                    errors.append(f'{relative}: broken local link {target}')
    if errors:
        raise RuntimeError('\n'.join(errors))
    return public_files()


if __name__ == '__main__':
    files = check()
    print(f'PASS: {len(files)} public source files; known secret patterns and local Markdown links checked.')
