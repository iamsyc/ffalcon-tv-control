#!/usr/bin/env python3
"""On-device regression: identical scrcpy clicks must open TCL's app drawer."""
import argparse, pathlib, socket, struct, subprocess, time, xml.etree.ElementTree as ET, json
root=pathlib.Path(__file__).resolve().parent
adb=root/'adb-tv'
def run(*args):return subprocess.check_output([str(adb),*map(str,args)],text=True)
def texts():
    run('shell','uiautomator dump /data/local/tmp/tv-button-test.xml')
    return [n.get('text') for n in ET.fromstring(run('shell','cat /data/local/tmp/tv-button-test.xml')).iter('node') if n.get('text')]
def touch(sock,action,x,y):
    sock.sendall(struct.pack('>BBqiiHHHII',2,action,-1,x,y,1920,1080,65535 if action!=1 else 0,1 if action!=2 else 0,0 if action==1 else 1))
p=argparse.ArgumentParser();p.add_argument('server',type=pathlib.Path);p.add_argument('--drag',action='store_true');args=p.parse_args()
run('shell','input keyevent KEYCODE_HOME');before=texts();assert '打开信号源面板' in before,before
remote='/data/local/tmp/tv-button-test-server.jar';run('push',args.server,remote)
scid=0x7476431
port=run('forward','tcp:0',f'localabstract:scrcpy_{scid:08x}').strip()
logdir=root.parents[1]/'.local/device-checks';logdir.mkdir(parents=True,exist_ok=True)
logfile=logdir/('wire-drag.log' if args.drag else 'wire-click.log')
with logfile.open('w') as log:
    server=subprocess.Popen([str(adb),'shell',f'CLASSPATH={remote} app_process / com.genymobile.scrcpy.Server 5.0.1 scid={scid:08x} video=false audio=false tunnel_forward=true cleanup=false power_on=false clipboard_autosync=false log_level=debug'],stdout=log,stderr=subprocess.STDOUT)
    sock=None
    try:
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            try:
                sock=socket.create_connection(('127.0.0.1',int(port)),timeout=1)
                header=b''
                while len(header)<65:
                    part=sock.recv(65-len(header))
                    if not part:raise ConnectionError('server not ready')
                    header+=part
                break
            except (OSError,ConnectionError):
                if sock:sock.close()
                sock=None;time.sleep(.1)
        assert sock,'scrcpy handshake failed'
        touch(sock,0,1146,572)
        if args.drag:touch(sock,2,1146,422)
        touch(sock,1,1146,422 if args.drag else 572)
        time.sleep(.8)
    finally:
        if sock:sock.close()
        try:server.wait(timeout=5)
        except subprocess.TimeoutExpired:server.terminate();server.wait(timeout=5)
        run('forward','--remove','tcp:'+port)
after=texts();opened='应用推荐' in after and '系统应用' in after
result={'server':str(args.server),'drag':args.drag,'drawer_opened':opened,'passed':not opened if args.drag else opened,'texts':after}
print(json.dumps(result,ensure_ascii=False,indent=2))
raise SystemExit(0 if result['passed'] else 1)
