"""Shared configuration and the verified ADB reconnection procedure."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import time

SUPPORT = Path(os.environ.get('TV_CONTROL_HOME', Path.home() / 'Library/Application Support/TVControl'))
CONFIG = SUPPORT / 'connection.json'
ADB = shutil.which('adb') or 'adb'


def config():
    return json.loads(CONFIG.read_text())


def adb_env(c):
    env = os.environ.copy()
    env['ADB_VENDOR_KEYS'] = c['adb_key']
    env['ANDROID_USER_HOME'] = str(Path(c['adb_key']).parent)
    env['ADB_SERVER_SOCKET'] = 'tcp:localhost:' + str(c['adb_server_port'])
    return env


def run_adb(c, args, timeout=10, binary=False):
    return subprocess.run([c.get('adb_path', ADB)] + args, env=adb_env(c),
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
