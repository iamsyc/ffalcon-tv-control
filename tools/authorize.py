"""Prepare, apply and restore the firmware-specific IpelEngine authorization change."""
from pathlib import Path
import hashlib
import json
import time
import urllib.error
import urllib.request

URI = 'content://com.tcl.providers.config/IpelEngine'
KEY_PATH = '/data/misc/adb/adb_keys'


class Helper:
    def __init__(self, settings):
        self.base = f"http://{settings['host']}:{int(settings.get('port', 8765))}/{settings['token']}/"
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request(self, route, body=None):
        data = None if body is None else json.dumps(body, ensure_ascii=False).encode()
        request = urllib.request.Request(self.base + route, data=data,
                                         headers={'Content-Type': 'application/json'})
        try:
            with self.opener.open(request, timeout=15) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as error:
            error.close()
            raise

    def query(self):
        rows = self.request('query', {'uri': URI, 'columns': ['project_id', 'config_content']})['rows']
        if len(rows) != 1 or rows[0]['project_id'] != 'IpelEngine':
            raise RuntimeError('IpelEngine 行结构与实测环境不一致。停止此授权路径。')
        return rows[0]['config_content']

    def update(self, text):
        result = self.request('provider', {'operation': 'update', 'uri': URI,
                                          'values': {'config_content': text}})
        if result.get('updated') != 1:
            raise RuntimeError('IpelEngine update 未返回 updated=1。')
        return result


def candidate(original, key):
    data = json.loads(original)
    groups = [item for item in data if item.get('name') == 'ipelNode']
    if len(groups) != 1 or not isinstance(groups[0].get('value'), list):
        raise RuntimeError('未找到已验证的 ipelNode 列表，停止。')
    nodes = groups[0]['value']
    if any(node.get('path') == KEY_PATH for node in nodes):
        raise RuntimeError('配置已包含 ADB 授权文件节点。先检查并恢复遗留实验配置。')
    if len(key.split()) < 2 or '\n' in key:
        raise ValueError('需要 adb keygen 生成的单行 .pub 文件。')
    nodes.append({'path': KEY_PATH, 'value': key + '\n'})
    return json.dumps(data, ensure_ascii=False, separators=(',', ':'))


def prepare(helper, public_key, output):
    status = helper.request('status')
    if status.get('version') != 9 or not status.get('page_control'):
        raise RuntimeError('需要诊断工具协议 v9，并在电视上启用电脑控制。')
    original = helper.query()
    key = Path(public_key).read_text().strip()
    updated = candidate(original, key)
    plan = {'format': 1, 'uri': URI, 'target': KEY_PATH,
            'effect': '替换电视现有 ADB 授权列表。旧列表无法在此阶段读取或备份。',
            'public_key': key, 'public_key_sha256': hashlib.sha256(key.encode()).hexdigest(),
            'original_config': original, 'candidate_config': updated}
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n')
    output.chmod(0o600)
    return plan


def restore(helper, plan):
    if plan['candidate_config'] != candidate(plan['original_config'], plan['public_key']):
        raise ValueError('计划包含预期公钥写入以外的配置变更，停止。')
    helper.update(plan['original_config'])
    if helper.query() != plan['original_config']:
        raise RuntimeError('IpelEngine 配置未精确恢复。保留计划文件，执行 authorize-restore。')


def apply(helper, plan, allow_replace=False):
    if not allow_replace:
        raise RuntimeError('必须显式指定 --replace-adb-authorizations，确认覆盖已有电脑授权。')
    if plan['uri'] != URI or plan['target'] != KEY_PATH:
        raise ValueError('授权计划的目标与本工具固定路径不一致。')
    if plan['candidate_config'] != candidate(plan['original_config'], plan['public_key']):
        raise ValueError('计划包含预期公钥写入以外的配置变更，停止。')
    if helper.query() != plan['original_config']:
        raise RuntimeError('当前 IpelEngine 配置已变化，停止使用旧计划。重新读取并准备。')
    try:
        helper.update(plan['candidate_config'])
        time.sleep(2)
    finally:
        try:
            restore(helper, plan)
        except Exception as error:
            raise RuntimeError('IpelEngine 恢复失败。保留计划文件并执行 authorize-restore。') from error
    return {'config_restored_exactly': True,
            'adb_authorized': 'unverified',
            'next': '重启专用 ADB server，再执行 connect 和 adb shell id 验证。'}
