import copy
import http.server
import json
import pathlib
import sys
import tempfile
import threading
import unittest
import urllib.error
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
import authorize


class AuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = pathlib.Path(self.tmp.name)
        self.original = '[{"name":"enable","value":"true"},{"name":"ipelNode","value":[{"path":"/sys/example","value":"1"}]}]'
        self.current = self.original
        self.updates = []
        self.fail_candidate = False
        self.fail_restore = False
        owner = self
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):pass
            def answer(self, code, data):
                self.send_response(code);self.end_headers();self.wfile.write(json.dumps(data).encode())
            def do_GET(self):
                self.answer(200, {'version': 9, 'page_control': True})
            def do_POST(self):
                data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                if self.path.endswith('/query'):
                    return self.answer(200, {'rows': [{'project_id': 'IpelEngine', 'config_content': owner.current}]})
                if not self.path.endswith('/provider') or data.get('uri') != authorize.URI:
                    return self.answer(400, {})
                text = data['values']['config_content'];owner.updates.append(text)
                is_restore = text == owner.original
                if (is_restore and owner.fail_restore) or (not is_restore and owner.fail_candidate):
                    return self.answer(500, {})
                owner.current = text;self.answer(200, {'updated': 1})
        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True);thread.start()
        self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)
        self.helper = authorize.Helper({'host': '127.0.0.1', 'port': self.server.server_port,
                                        'token': '0123456789abcdef0123456789abcdef'})
        self.key = self.folder / 'adbkey.pub';self.key.write_text('QUJDRA== test-device\n')

    def plan(self):
        return authorize.prepare(self.helper, self.key, self.folder/'plan.json')

    def test_plan_is_read_only_and_preserves_original(self):
        plan = self.plan()
        self.assertEqual(self.updates, [])
        self.assertEqual(plan['original_config'], self.original)
        node = json.loads(plan['candidate_config'])[1]['value'][-1]
        self.assertEqual(node, {'path': authorize.KEY_PATH, 'value': self.key.read_text()})

    def test_apply_and_exact_restore_over_real_http(self):
        plan = self.plan()
        with patch.object(authorize.time, 'sleep'):
            result = authorize.apply(self.helper, plan, True)
        self.assertEqual(self.updates, [plan['candidate_config'], self.original])
        self.assertEqual(self.current, self.original)
        self.assertTrue(result['config_restored_exactly'])
        self.assertEqual(result['adb_authorized'], 'unverified')

    def test_missing_owner_flag_does_not_update(self):
        with self.assertRaisesRegex(RuntimeError, 'replace-adb-authorizations'):
            authorize.apply(self.helper, self.plan())
        self.assertEqual(self.updates, [])

    def test_stale_plan_does_not_overwrite_new_configuration(self):
        plan = self.plan();self.current = '[]'
        with self.assertRaisesRegex(RuntimeError, '已变化'):
            authorize.apply(self.helper, plan, True)
        self.assertEqual(self.updates, [])

    def test_extra_payload_changes_are_rejected(self):
        plan = self.plan();data = json.loads(plan['candidate_config']);data[0]['value'] = 'false'
        plan['candidate_config'] = json.dumps(data)
        with self.assertRaisesRegex(ValueError, '以外'):
            authorize.apply(self.helper, plan, True)
        self.assertEqual(self.updates, [])

    def test_update_error_still_restores_original(self):
        plan = self.plan();self.fail_candidate = True
        with self.assertRaises(urllib.error.HTTPError):
            authorize.apply(self.helper, plan, True)
        self.assertEqual(self.updates[-1], self.original)
        self.assertEqual(self.current, self.original)

    def test_invalid_restore_plan_does_not_write(self):
        plan = self.plan();plan['candidate_config'] = '[]'
        with self.assertRaises(ValueError):
            authorize.restore(self.helper, plan)
        self.assertEqual(self.updates, [])

    def test_restore_failure_is_not_reported_as_success(self):
        plan = self.plan();self.fail_restore = True
        with patch.object(authorize.time, 'sleep'), self.assertRaisesRegex(RuntimeError, '恢复失败'):
            authorize.apply(self.helper, plan, True)
        self.assertEqual(self.current, plan['candidate_config'])


if __name__ == '__main__':unittest.main()
