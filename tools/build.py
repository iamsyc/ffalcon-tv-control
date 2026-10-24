#!/usr/bin/env python3
"""Build the diagnostic APK, patched scrcpy server and native macOS applications."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import plistlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / '.build'
VERSIONS = json.loads((ROOT / 'versions.json').read_text())


def run(args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, **kwargs)


def sdk_paths():
    sdk = os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT')
    if not sdk:raise RuntimeError('设置 ANDROID_HOME，安装 platform 35 与 build-tools 35.0.0。')
    sdk = Path(sdk)
    platform = sdk / f"platforms/android-{VERSIONS['android_platform']}"
    tools = sdk / 'build-tools' / VERSIONS['android_build_tools']
    if not (platform / 'android.jar').is_file() or not (tools / 'd8').is_file():
        raise RuntimeError('Android SDK 缺少指定 platform 或 build-tools，参见 docs/build.md。')
    return sdk, platform, tools


def helper():
    sdk, platform, tools = sdk_paths()
    source = ROOT / 'android/helper'
    work = BUILD / 'helper'
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='compile-', dir=work) as tmp:
        temp = Path(tmp);generated = temp / 'generated';classes = temp / 'classes';dex = temp / 'dex'
        for folder in [generated, classes, dex]:folder.mkdir()
        archive = temp / 'unsigned.apk'
        run([tools/'aapt', 'package', '-f', '-m', '-J', generated, '-M', source/'AndroidManifest.xml',
             '-S', source/'res', '-I', platform/'android.jar', '-F', archive])
        sources = list((source/'local').rglob('*.java')) + list(generated.rglob('*.java'))
        run(['javac', '-encoding', 'UTF-8', '-source', '8', '-target', '8', '-classpath',
             platform/'android.jar', '-d', classes, *sources])
        run([tools/'d8', '--lib', platform/'android.jar', '--min-api', '34', '--output', dex,
             *classes.rglob('*.class')])
        with zipfile.ZipFile(archive, 'a', compression=zipfile.ZIP_DEFLATED) as out:
            for file in dex.glob('classes*.dex'):out.write(file, file.name)
        aligned = temp / 'aligned.apk';run([tools/'zipalign', '-f', '4', archive, aligned])
        key = Path(os.environ.get('TV_APK_KEYSTORE', ROOT/'.local/helper.keystore'))
        key.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        env = os.environ.copy();env.setdefault('TV_APK_KEYSTORE_PASSWORD', 'changeit')
        alias = env.get('TV_APK_KEY_ALIAS', 'tv-diagnostic')
        if not key.exists():
            run(['keytool', '-genkeypair', '-keystore', key, '-storepass:env', 'TV_APK_KEYSTORE_PASSWORD',
                 '-keypass:env', 'TV_APK_KEYSTORE_PASSWORD', '-alias', alias, '-keyalg', 'RSA',
                 '-keysize', '2048', '-validity', '10000', '-dname', 'CN=TV diagnostics'], env=env)
        key.chmod(0o600)
        output = work / 'tv-debug-entry-v9.apk'
        run([tools/'apksigner', 'sign', '--ks', key, '--ks-pass', 'env:TV_APK_KEYSTORE_PASSWORD',
             '--ks-key-alias', alias, '--out', output, aligned], env=env)
        run([tools/'apksigner', 'verify', output]);run([tools/'zipalign', '-c', '4', output])
    print('APK:', output)


def server():
    sdk, platform, tools = sdk_paths()
    cache = ROOT / '.cache';cache.mkdir(exist_ok=True)
    archive = cache / 'scrcpy-5.0.1.tar.gz'
    if not archive.exists():
        with urllib.request.urlopen(VERSIONS['scrcpy_source_url'], timeout=30) as response:
            archive.write_bytes(response.read())
    if hashlib.sha256(archive.read_bytes()).hexdigest() != VERSIONS['scrcpy_source_sha256']:
        raise RuntimeError('上游源码归档 SHA-256 不匹配，停止构建。')
    (BUILD/'server').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='scrcpy-source-', dir=BUILD) as tmp:
        temp = Path(tmp)
        with tarfile.open(archive) as tar:tar.extractall(temp, filter='data')
        source = temp / 'scrcpy-5.0.1'
        run(['patch', '--batch', '-p1', '-i', ROOT/'patches/scrcpy-5.0.1-tcl-input.patch'], cwd=source)
        env = os.environ.copy();env.update(ANDROID_HOME=str(sdk), ANDROID_PLATFORM=str(VERSIONS['android_platform']),
              ANDROID_BUILD_TOOLS=VERSIONS['android_build_tools'], BUILD_DIR=str(BUILD/'server'))
        run(['bash', './build_without_gradle.sh'], cwd=source/'server', env=env)
    print('Server:', BUILD/'server/scrcpy-server')


def macos(install=False):
    if sys.platform != 'darwin':raise RuntimeError('原生控制台构建需要 macOS。')
    applications = [('客厅电视', 'TVControl', 'local.tv.scrcpy.control'),
                    ('电视控制台', 'TVConsole', 'local.tv.console')]
    if install:
        for name, _, _ in applications:
            destination = Path.home()/'Applications'/(name+'.app')
            if destination.exists():
                raise RuntimeError(f'{destination} 已存在。关闭应用后在 Finder 中明确替换，构建脚本不覆盖现有安装。')
    scrcpy = shutil.which('scrcpy')
    if not scrcpy:raise RuntimeError('未找到 scrcpy。')
    version = subprocess.check_output([scrcpy, '--version'], text=True).splitlines()[0].split()[1]
    if version != VERSIONS['scrcpy_version']:raise RuntimeError('client/server 必须同为 scrcpy '+VERSIONS['scrcpy_version'])
    patched = BUILD/'server/scrcpy-server'
    if not patched.exists():raise RuntimeError('先构建 server。')
    apps = BUILD/'apps';apps.mkdir(parents=True, exist_ok=True)
    iconset = BUILD/'TVConsole.iconset'
    run(['swift', ROOT/'macos/TVConsoleIcon.swift', iconset])
    icon = BUILD/'TVConsole.icns'
    run(['iconutil', '-c', 'icns', iconset, '-o', icon])
    for name, executable, identifier in applications:
        bundle = apps/(name+'.app');contents = bundle/'Contents';bin_dir = contents/'MacOS';resources = contents/'Resources'
        bin_dir.mkdir(parents=True, exist_ok=True);resources.mkdir(exist_ok=True)
        info = {'CFBundleName': name, 'CFBundleDisplayName': name, 'CFBundleExecutable': executable,
                'CFBundleIdentifier': identifier, 'CFBundlePackageType': 'APPL',
                'CFBundleShortVersionString': VERSIONS['project_version'], 'CFBundleVersion': '1',
                'NSHighResolutionCapable': True, 'LSMultipleInstancesProhibited': True,
                'NSPrincipalClass': 'NSApplication', 'TVPythonExecutable': sys.executable}
        if executable == 'TVConsole':info['CFBundleIconFile'] = 'TVConsole'
        (contents/'Info.plist').write_bytes(plistlib.dumps(info))
        shutil.copy2(ROOT/'runtime/tv_connection.py', resources/'tv_connection.py')
        if executable == 'TVControl':
            script=(ROOT/'macos/TVControl.py').read_text().split('\n',1)[1]
            (bin_dir/executable).write_text('#!'+sys.executable+'\n'+script);(bin_dir/executable).chmod(0o755)
            engine = bin_dir/'ScrcpyEngine';engine.unlink(missing_ok=True)
            shutil.copy2(scrcpy, engine);shutil.copy2(patched, resources/'scrcpy-server-tv')
        else:
            shutil.copy2(icon, resources/'TVConsole.icns')
            run(['swiftc', ROOT/'macos/TVConsole.swift', '-o', bin_dir/executable,
                 '-framework', 'AppKit', '-framework', 'UniformTypeIdentifiers'])
            shutil.copy2(ROOT/'macos/backend.py', resources/'backend.py')
        run(['codesign', '--force', '--sign', '-', '--timestamp=none', bundle])
        run(['codesign', '--verify', '--deep', '--strict', bundle])
        if install:
            destination=Path.home()/'Applications'/bundle.name
            destination.parent.mkdir(exist_ok=True);shutil.copytree(bundle,destination)
        print('App:', bundle)


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('target', choices=['helper','server','macos','all'])
    p.add_argument('--install', action='store_true', help='仅 macos/all，将首次安装复制到 ~/Applications')
    a=p.parse_args();BUILD.mkdir(exist_ok=True)
    try:
        if a.target in ('helper','all'):helper()
        if a.target in ('server','all'):server()
        if a.target in ('macos','all'):macos(a.install)
    except (OSError,RuntimeError,subprocess.CalledProcessError) as error:
        print(str(error),file=sys.stderr);raise SystemExit(1)
