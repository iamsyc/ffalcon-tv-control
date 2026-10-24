import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'runtime'))
import tv_connection as tv


class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.config=pathlib.Path(self.tmp.name)/'connection.json'
        self.c={'target':'192.0.2.10:34961','adb_server_port':5041,'adb_key':'fixture/adbkey'}
        self.config.write_text(json.dumps(self.c));self.calls=[];self.clock=0
        p=patch.object(tv,'CONFIG',self.config);p.start();self.addCleanup(p.stop)
        p=patch.object(tv.time,'monotonic',side_effect=lambda:self.clock);p.start();self.addCleanup(p.stop)
        p=patch.object(tv.time,'sleep',side_effect=self.sleep);p.start();self.addCleanup(p.stop)

    def sleep(self,value):self.clock+=value

    def test_fixed_device_is_reused_without_restarting(self):
        def run(c,args,**kwargs):
            self.calls.append(args)
            return subprocess.CompletedProcess(args,0,'device\n' if args[-1]=='get-state' else 'already connected\n','')
        with patch.object(tv,'run_adb',side_effect=run):result=tv.ensure_connection()
        self.assertEqual(result['target'],'192.0.2.10:5555')
        self.assertFalse(any('tcpip' in call for call in self.calls))

    def test_failed_connect_text_is_not_authorization_and_mdns_recovers(self):
        restored=False
        def run(c,args,**kwargs):
            nonlocal restored
            self.calls.append(args)
            if args==['mdns','services']:
                text='other _adb._tcp 192.0.2.99:5555\ntv _adb-tls-connect._tcp 192.0.2.10:40000\n'
                return subprocess.CompletedProcess(args,0,text,'')
            if 'tcpip' in args:restored=True
            if args[-1]=='get-state':
                ok=args[1]=='192.0.2.10:40000' or (restored and args[1]=='192.0.2.10:5555')
                return subprocess.CompletedProcess(args,0 if ok else 1,'device\n' if ok else '', 'offline' if not ok else '')
            return subprocess.CompletedProcess(args,0,'failed to connect\n','')
        with patch.object(tv,'run_adb',side_effect=run):result=tv.ensure_connection()
        self.assertEqual(result['target'],'192.0.2.10:5555')
        self.assertIn(['-s','192.0.2.10:40000','tcpip','5555'],self.calls)
        self.assertFalse(any('192.0.2.99:5555' in call for call in self.calls))

    def test_unauthorized_service_does_not_restart_adbd(self):
        def run(c,args,**kwargs):
            self.calls.append(args)
            output='tv _adb-tls-connect._tcp 192.0.2.10:40000\n' if args==['mdns','services'] else 'unauthorized\n'
            return subprocess.CompletedProcess(args,0,output,'')
        with patch.object(tv,'run_adb',side_effect=run),self.assertRaisesRegex(RuntimeError,'已授权'):
            tv.ensure_connection()
        self.assertFalse(any('tcpip' in call for call in self.calls))
        self.assertEqual(json.loads(self.config.read_text()),self.c)


if __name__=='__main__':unittest.main()
