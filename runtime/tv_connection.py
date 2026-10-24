"""Shared configuration and the verified ADB reconnection procedure."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time

SUPPORT = Path(os.environ.get('TV_CONTROL_HOME', Path.home() / 'Library/Application Support/TVControl'))
CONFIG = SUPPORT / 'connection.json'
ADB = shutil.which('adb') or 'adb'


def config():
    return json.loads(CONFIG.read_text())


def adb_env(c):
    key = Path(c['adb_key']).resolve()
    if not key.is_file():
        raise RuntimeError('本机 ADB 密钥不存在，请恢复原密钥；不会自动生成新身份。')
    state = CONFIG.parent.resolve()
    identity = hashlib.sha256(str(state).encode() + b'\0' + key.read_bytes()).hexdigest()[:20]
    home = state / 'adb' / identity
    android = home / '.android'
    android.mkdir(parents=True, exist_ok=True, mode=0o700)
    link = android / 'adbkey'
    try:
        link.symlink_to(key)
    except FileExistsError:
        if not link.is_symlink() or link.resolve() != key:
            raise RuntimeError('专用 ADB 目录中的密钥与配置不一致，请检查本机状态目录。')
    sockets = Path(tempfile.gettempdir()) / ('tvcontrol-' + str(os.getuid()))
    sockets.mkdir(exist_ok=True, mode=0o700)
    sockets.chmod(0o700)
    env = os.environ.copy()
    # Only ADB and scrcpy children use this home; the user's HOME stays unchanged.
    env['HOME'] = str(home)
    env.pop('ADB_VENDOR_KEYS', None)
    env.pop('ANDROID_USER_HOME', None)
    env['ADB_SERVER_SOCKET'] = 'localfilesystem:' + str(sockets / (identity + '.sock'))
    return env


def ensure_server(c):
    env = adb_env(c)
    result = subprocess.run([c.get('adb_path', ADB), 'server-status'], env=env,
                            capture_output=True, text=True, timeout=10)
    result.check_returncode()
    field = next((line.split(': ', 1)[1] for line in result.stdout.splitlines()
                  if line.startswith('keystore_path: ')), None)
    if field is None:
        raise RuntimeError('ADB 未提供密钥路径，请安装 Android Platform Tools 37.0.1 或更高版本。')
    if Path(json.loads(field)) != Path(env['HOME']) / '.android/adbkey':
        raise RuntimeError('ADB 服务加载了其他密钥，拒绝复用或重启该服务。')
    return env


def run_adb(c, args, timeout=10, binary=False):
    return subprocess.run([c.get('adb_path', ADB)] + args, env=ensure_server(c),
                          capture_output=True, text=not binary, timeout=timeout)


def connected(c, target):
    try:
        run_adb(c, ['connect', target], timeout=5)
        result = run_adb(c, ['-s', target, 'get-state'], timeout=5)
        return result.returncode == 0 and result.stdout.strip() == 'device'
    except subprocess.TimeoutExpired:
        return False


def ensure_connection():
    c = config()
    host = c['target'].rsplit(':', 1)[0]
    fixed = host + ':5555'
    candidates = list(dict.fromkeys([fixed, c['target']]))
    target = next((value for value in candidates if connected(c, value)), None)
    discovery_deadline = time.monotonic() + 5
    while target is None and time.monotonic() < discovery_deadline:
        services = run_adb(c, ['mdns', 'services']).stdout
        for line in services.splitlines():
            fields = line.split()
            if len(fields) != 3 or fields[1] not in ('_adb._tcp', '_adb-tls-connect._tcp'):
                continue
            address = fields[2]
            if address.rsplit(':', 1)[0] == host and connected(c, address):
                target = address
                break
        if target is None:
            time.sleep(0.5)
    if target is None:
        raise RuntimeError('未找到已授权的电视 ADB 服务。确认电视开机、ADB 开启，或更新当前连接端口。')
    if target != fixed:
        result = run_adb(c, ['-s', target, 'tcpip', '5555'])
        if result.returncode:
            raise RuntimeError((result.stdout + result.stderr).strip())
        deadline = time.monotonic() + 15
        while not connected(c, fixed):
            if time.monotonic() >= deadline:
                raise RuntimeError('已请求固定端口，但 5555 连接失败。确认 ADB 仍已开启。')
            time.sleep(0.3)
    c['target'] = fixed
    CONFIG.write_text(json.dumps(c, ensure_ascii=False, indent=2) + '\n')
    return c
