#!/usr/bin/env python3
"""Local project entry point. Does not modify the TV without an explicit command."""
from pathlib import Path
import argparse
import getpass
import ipaddress
import json
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runtime'))
from tv_connection import SUPPORT, CONFIG, config, run_adb, ensure_connection, ensure_server
from authorize import Helper, prepare, apply, restore


def write_private(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    path.chmod(0o600)


def main(argv=None):
    parser = argparse.ArgumentParser(description='电视 ADB 初始化、授权和连接工具')
    commands = parser.add_subparsers(dest='action', required=True)
    init = commands.add_parser('init', help='仅创建本机配置和独立密钥')
    init.add_argument('--host', required=True)
    init.add_argument('--port', type=int, required=True, help='电视 ADB 开关旁显示的当前端口')
    helper = commands.add_parser('helper-config', help='保存诊断服务地址；交互输入凭据')
    helper.add_argument('--host', required=True)
    helper.add_argument('--port', type=int, default=8765)
    commands.add_parser('helper-status')
    plan = commands.add_parser('authorize-plan', help='读取配置并生成计划，不修改电视')
    plan.add_argument('--output', type=Path, default=SUPPORT / 'authorization-plan.json')
    for action in ['authorize-apply', 'authorize-restore']:
        item = commands.add_parser(action)
        item.add_argument('--plan', type=Path, default=SUPPORT / 'authorization-plan.json')
        if action == 'authorize-apply':item.add_argument('--replace-adb-authorizations', action='store_true')
    connect = commands.add_parser('connect', help='仅用于已授权的 ADB；发现端口并恢复 5555')
    connect.add_argument('--port', type=int, help='mDNS 不可用时更新电视当前端口')
    commands.add_parser('server-restart', help='重启配置中指定的本机专用 ADB server')
    commands.add_parser('status', help='只读验证已保存的连接，不切换端口')
    commands.add_parser('doctor', help='只读检查本机工具与配置状态')
    adb = commands.add_parser('adb', help='对配置中的电视执行原生 adb 参数')
    adb.add_argument('args', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if args.action == 'doctor':
        result = {'config_exists': CONFIG.is_file(), 'state_dir': str(SUPPORT),
                  'tools': {name: shutil.which(name) for name in ['adb', 'scrcpy', 'java', 'javac', 'swiftc']}}
        if result['tools']['scrcpy']:
            result['scrcpy_version'] = subprocess.check_output([result['tools']['scrcpy'], '--version'], text=True).splitlines()[0]
        print(json.dumps(result, ensure_ascii=False, indent=2));return 0
    if args.action == 'init':
        ipaddress.IPv4Address(args.host)
        if not 0 < args.port <= 65535:
            raise ValueError('端口范围为 1 到 65535。')
        if CONFIG.exists():raise RuntimeError('配置已存在，init 不覆盖。更新端口使用 connect --port。')
        adb_path = shutil.which('adb')
        if not adb_path:raise RuntimeError('未找到 adb，请安装 Android Platform Tools。')
        key = SUPPORT / 'keys/adbkey'
        key.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not key.exists():subprocess.run([adb_path, 'keygen', str(key)], check=True, capture_output=True)
        key.chmod(0o600)
        write_private(CONFIG, {'target': f'{args.host}:{args.port}',
                               'adb_key': str(key), 'adb_path': adb_path})
        print('已创建本机配置和密钥，未连接或修改电视。');return 0
    if args.action == 'helper-config':
        ipaddress.IPv4Address(args.host)
        token = getpass.getpass('输入电视诊断页面路径中的 32 位凭据: ').strip()
        if len(token) != 32 or any(c not in '0123456789abcdef' for c in token):
            raise ValueError('凭据应为 32 位小写十六进制。')
        write_private(SUPPORT / 'helper.json', {'host': args.host, 'port': args.port, 'token': token})
        print('诊断服务连接信息已保存在本机。');return 0
    if args.action.startswith('authorize-') or args.action == 'helper-status':
        helper = Helper(json.loads((SUPPORT / 'helper.json').read_text()))
        if args.action == 'helper-status':result = helper.request('status')
        elif args.action == 'authorize-plan':
            plan = prepare(helper, Path(config()['adb_key'] + '.pub'), args.output)
            result = {'plan': str(args.output), 'target': plan['target'], 'effect': plan['effect'],
                      'public_key_sha256': plan['public_key_sha256'], 'tv_modified': False}
        else:
            plan = json.loads(args.plan.read_text())
            if args.action == 'authorize-apply':
                if plan['public_key'] != Path(config()['adb_key'] + '.pub').read_text().strip():
                    raise RuntimeError('计划公钥与本机当前密钥不一致，重新生成授权计划。')
                result = apply(helper, plan, args.replace_adb_authorizations)
            else:restore(helper, plan);result = {'config_restored_exactly': True, 'adb_keys_restored': False}
        print(json.dumps(result, ensure_ascii=False, indent=2));return 0
    c = config()
    if args.action == 'connect':
        if args.port:
            if not 0 < args.port <= 65535:raise ValueError('端口范围为 1 到 65535。')
            c['target'] = c['target'].rsplit(':', 1)[0] + ':' + str(args.port);write_private(CONFIG, c)
        c = ensure_connection()
        result = run_adb(c, ['-s', c['target'], 'shell', 'id'])
    elif args.action == 'server-restart':
        run_adb(c, ['kill-server']).check_returncode()
        result = run_adb(c, ['start-server'])
    elif args.action == 'status':result = run_adb(c, ['-s', c['target'], 'get-state'])
    else:
        if not args.args:raise ValueError('adb 子命令为空。')
        return subprocess.run([c['adb_path'], '-s', c['target']] + args.args,
                              env=ensure_server(c)).returncode
    print(result.stdout.strip())
    if result.stderr:print(result.stderr.strip(), file=sys.stderr)
    return result.returncode


if __name__ == '__main__':
    try:raise SystemExit(main())
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr);raise SystemExit(1)
