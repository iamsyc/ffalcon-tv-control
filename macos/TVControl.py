#!/usr/bin/env python3
from pathlib import Path
import os,json,subprocess,sys
sys.dont_write_bytecode = True
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"Resources"))
from tv_connection import ensure_connection, adb_env
mac=Path(__file__).resolve().parent
resources=mac.parent/'Resources'
config=ensure_connection()
env=adb_env(config)
env['PATH']=str(Path(config['adb_path']).parent)+':'+env.get('PATH','')
env['ADB']=config['adb_path']
env['SCRCPY_SERVER_PATH']=str(resources/'scrcpy-server-tv')
log=Path.home()/'Library/Logs/TVControl'
log.mkdir(parents=True,exist_ok=True)
fd=os.open(str(log/'scrcpy.log'),os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
os.dup2(fd,1);os.dup2(fd,2);os.close(fd)
args=[str(mac/'ScrcpyEngine'),'--serial='+config['target'],'--no-audio','--no-clipboard-autosync','--no-power-on','--max-size=1280','--max-fps=45','--window-title=客厅电视 · 实时控制','--window-width=1100']
os.execve(args[0],args,env)
