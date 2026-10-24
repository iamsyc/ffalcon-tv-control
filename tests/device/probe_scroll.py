#!/usr/bin/env python3
import argparse, pathlib, socket, struct, subprocess, time, xml.etree.ElementTree as ET, json
ROOT=pathlib.Path(__file__).resolve().parents[2]
ADB=ROOT/'tests/device/adb-tv'
def run(*args):return subprocess.check_output([str(ADB),*map(str,args)],text=True)
def snapshot():
 run('shell','uiautomator dump /data/local/tmp/tv-scroll-probe.xml >/dev/null')
 tree=ET.fromstring(run('shell','cat /data/local/tmp/tv-scroll-probe.xml'))
 return [{'text':n.get('text'),'id':n.get('resource-id'),'bounds':n.get('bounds'),'focused':n.get('focused'),'scrollable':n.get('scrollable')} for n in tree.iter('node') if n.get('text') or n.get('scrollable')=='true']
class Control:
 def __init__(self,server,log):
  self.remote='/data/local/tmp/tv-scroll-probe.jar';run('push',server,self.remote)
  self.scid=0x5653432
  self.port=run('forward','tcp:0',f'localabstract:scrcpy_{self.scid:08x}').strip()
  self.log=open(log,'w')
  self.process=subprocess.Popen([str(ADB),'shell',f'CLASSPATH={self.remote} app_process / com.genymobile.scrcpy.Server 5.0.1 scid={self.scid:08x} video=false audio=false tunnel_forward=true cleanup=false power_on=false clipboard_autosync=false log_level=debug'],stdout=self.log,stderr=subprocess.STDOUT)
  deadline=time.monotonic()+8
  while True:
   try:
    self.sock=socket.create_connection(('127.0.0.1',int(self.port)),timeout=1)
    data=b''
    while len(data)<65:
     part=self.sock.recv(65-len(data))
     if not part:raise ConnectionError('not ready')
     data+=part
    break
   except (ConnectionError,OSError):
    if time.monotonic()>deadline:raise
    time.sleep(.1)
 def scroll(self,x,y,v,h=0):self.sock.sendall(struct.pack('>BiiHHhhI',3,x,y,1920,1080,round(h*2048),round(v*2048),0))
 def touch(self,action,x,y):self.sock.sendall(struct.pack('>BBqiiHHHII',2,action,-1,x,y,1920,1080,0 if action==1 else 65535,1 if action in (0,1) else 0,0 if action==1 else 1))
 def close(self):
  self.sock.close()
  try:self.process.wait(timeout=5)
  except subprocess.TimeoutExpired:self.process.terminate();self.process.wait(timeout=5)
  run('forward','--remove','tcp:'+self.port);self.log.close()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--server',default=str(ROOT/'.build/server/scrcpy-server'));p.add_argument('--app',choices=['home','helper'],default='home');p.add_argument('--value',type=float,default=-1);p.add_argument('--count',type=int,default=20);p.add_argument('--output',required=True);a=p.parse_args()
 if a.app=='home':run('shell','input keyevent KEYCODE_HOME')
 else:run('shell','am start -n local.tv.debugentry/.MainActivity')
 before=snapshot();c=Control(a.server,a.output+'.log')
 try:
  start=time.monotonic()
  for i in range(a.count):c.scroll(1000,800,a.value);time.sleep(.0167)
  elapsed=time.monotonic()-start;time.sleep(.6)
 finally:c.close()
 after=snapshot()
 pathlib.Path(a.output).write_text(json.dumps({'app':a.app,'value':a.value,'count':a.count,'send_seconds':elapsed,'before':before,'after':after,'changed':before!=after},ensure_ascii=False,indent=2))
 print(json.dumps({'app':a.app,'value':a.value,'count':a.count,'changed':before!=after,'before_texts':[n['text'] for n in before][:8],'after_texts':[n['text'] for n in after][:8]},ensure_ascii=False))
