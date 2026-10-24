#!/usr/bin/env python3
import argparse,json,pathlib,socket,struct,subprocess,threading,time,statistics
from probe_scroll import run,ROOT
P=argparse.ArgumentParser();P.add_argument('--fps',type=int,required=True);P.add_argument('--server',default=str(ROOT/'.build/server/scrcpy-server'));P.add_argument('--app',choices=['home','helper'],default='helper');P.add_argument('--input',choices=['drag','wheel','keys','hold'],default='drag');P.add_argument('--size',type=int,default=1920);P.add_argument('--output',required=True);a=P.parse_args()
server=pathlib.Path(a.server);remote='/data/local/tmp/tv-scroll-video-probe.jar';run('push',server,remote)
run('shell','input keyevent KEYCODE_HOME' if a.app=='home' else 'am start -n local.tv.debugentry/.MainActivity')
scid=0x5653433;port=run('forward','tcp:0',f'localabstract:scrcpy_{scid:08x}').strip()
log=open(a.output+'.log','w');process=subprocess.Popen([str(ROOT/'tests/device/adb-tv'),'shell',f'CLASSPATH={remote} app_process / com.genymobile.scrcpy.Server 5.0.1 scid={scid:08x} audio=false tunnel_forward=true cleanup=false power_on=false clipboard_autosync=false max_fps={a.fps} max_size={a.size} video_bit_rate=8000000 log_level=debug'],stdout=log,stderr=subprocess.STDOUT)
def receive(s,n):
 result=b''
 while len(result)<n:
  data=s.recv(n-len(result))
  if not data:raise EOFError()
  result+=data
 return result
v=None;c=None;packets=[];sizes=[];reading=True
try:
 deadline=time.monotonic()+10
 while True:
  try:
   v=socket.create_connection(('127.0.0.1',int(port)),timeout=1);receive(v,1);break
  except (OSError,EOFError):
   if v:v.close()
   if time.monotonic()>deadline:raise
   time.sleep(.1)
 c=socket.create_connection(('127.0.0.1',int(port)),timeout=2);receive(v,64);codec=receive(v,4);v.settimeout(2)
 def read_video():
  try:
   while reading:
    hdr=receive(v,12);flags,value=struct.unpack('>QI',hdr)
    if flags&(1<<63):sizes.append(struct.unpack('>III',hdr)[1:]);continue
    payload=receive(v,value)
    if not flags&(1<<62):packets.append((flags&((1<<61)-1),time.monotonic(),len(payload)))
  except (OSError,EOFError):pass
 thread=threading.Thread(target=read_video,daemon=True);thread.start();time.sleep(1)
 def touch(action,y):
  w,h=sizes[-1]
  c.sendall(struct.pack('>BBqiiHHHII',2,action,-2,round(1860*w/1920),round(y*h/1080),w,h,0 if action==1 else 65535,0,0))
 start=time.monotonic()
 for swipe in range(8):
  y0,y1=(800,230) if swipe%2==0 else (230,800)
  if a.input=='drag':touch(0,y0)
  t=time.monotonic()
  for i in range(1,37):
   wait=t+i/60-time.monotonic()
   if wait>0:time.sleep(wait)
   if a.input=='drag':touch(2,y0+(y1-y0)*i/36)
   elif a.input=='hold':
    if i==1 or i%6==0:
     code=20 if swipe%2==0 else 19
     c.sendall(struct.pack('>BBIII',0,0,code,i//6,0))
   elif a.input=='keys':
    if i%9==0:
     code=20 if swipe%2==0 else 19
     c.sendall(struct.pack('>BBIII',0,0,code,0,0)+struct.pack('>BBIII',0,1,code,0,0))
   else:
    w,h=sizes[-1]
    c.sendall(struct.pack('>BiiHHhhI',3,round(1000*w/1920),round(800*h/1080),w,h,0,-246 if swipe%2==0 else 246,0))
  if a.input=='drag':touch(1,y1)
  if a.input=='hold':c.sendall(struct.pack('>BBIII',0,1,20 if swipe%2==0 else 19,0,0))
  time.sleep(.1)
 end=time.monotonic();time.sleep(.5)
 frames=[p for p in packets if start<=p[1]<=end]
 intervals=[(b[0]-x[0])/1000 for x,b in zip(frames,frames[1:])]
 arrivals=[(b[1]-x[1])*1000 for x,b in zip(frames,frames[1:])]
 def pct(values,q):return sorted(values)[round((len(values)-1)*q)] if values else None
 result={'fps_cap':a.fps,'size':a.size,'codec':codec.decode(errors='replace'),'video_sizes':sizes,'workload':a.app+' ScrollView, 8 alternating 600ms '+a.input+' sequences at 60 events/s, 100ms gaps','duration_s':end-start,'frames':len(frames),'received_fps':len(frames)/(end-start),'pts_interval_ms':{'median':statistics.median(intervals),'p95':pct(intervals,.95),'max':max(intervals)},'arrival_interval_ms':{'median':statistics.median(arrivals),'p95':pct(arrivals,.95),'max':max(arrivals)},'frame_samples':frames}
 pathlib.Path(a.output).write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='frame_samples'},indent=2))
finally:
 reading=False
 for s in [v,c]:
  if s:s.close()
 try:process.wait(timeout=5)
 except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=5)
 run('forward','--remove','tcp:'+port);log.close()
