#!/usr/bin/env python3
from pathlib import Path
import sys,os,json,subprocess,shlex,re,datetime,uuid
sys.dont_write_bytecode = True
from tv_connection import ensure_connection, SUPPORT, CONFIG, config, run_adb
NAMES={'local.tv.debugentry':'电视调试诊断','com.tcl.settings':'系统设置','com.tcl.MultiScreenInteraction_TV':'多屏互动','com.tcl.guard':'电视管家','com.tcl.ui_mediaCenter':'媒体中心','com.cibn.tv':'酷喵影视','com.kugou.tv':'酷狗音乐','com.tencent.qqmusictv':'QQ 音乐','com.xiaodianshi.tv.yst':'哔哩哔哩','com.tcl.gamecenter':'游戏中心','com.tcl.appreciate.art':'艺术展览','com.tcl.common.weather':'天气','com.tcl.ffeducation':'雷鸟教育','com.tcl.usercenter':'用户中心','com.tcl.appmarket2':'应用商店','com.tcl.tvsmartalbum':'智能相册','com.tcl.walleve':'智慧语音','com.tcl.wholenetsearch':'全网搜索','com.tcl.playskill':'玩机技巧','com.tcl.c2dm.client':'消息服务','com.tcl.tliveplay':'电视直播','com.tcl.t_solo':'蓝牙听音'}
def adb(args,timeout=25,binary=False):
 c=config();p=run_adb(c,['-s',c['target']]+args,timeout=timeout,binary=binary)
 if p.returncode:
  output=p.stderr+p.stdout
  raise RuntimeError(output.decode(errors='replace').strip() if binary else output.strip())
 return p.stdout if binary else p.stdout.strip()
def shell(*args,timeout=25):return adb(['shell',shlex.join(args)],timeout=timeout)
def apps():
 found={}
 for category in ['LEANBACK_LAUNCHER','LAUNCHER']:
  text=shell('cmd','package','query-activities','--brief','--components','-a','android.intent.action.MAIN','-c','android.intent.category.'+category)
  for component in text.splitlines():
   if not re.fullmatch(r'[\w.$]+/[\w.$]+',component):continue
   pkg=component.split('/')[0]
   if pkg not in found:found[pkg]={'package':pkg,'component':component,'name':NAMES.get(pkg,pkg),'tv':category=='LEANBACK_LAUNCHER'}
 return sorted(found.values(),key=lambda x:(x['package']!='local.tv.debugentry',x['name']))
def backup():
 folder=Path.home()/'Documents/电视配置备份'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
 folder.mkdir(parents=True,mode=0o700)
 for namespace in ['global','secure','system']:
  (folder/(namespace+'.txt')).write_text(shell('settings','list',namespace)+'\n')
 raw=shell('content','query','--uri','content://com.tcl.providers.config/all','--projection','project_id:config_content')
 (folder/'厂商配置原文.txt').write_text(raw+'\n')
 rows=[]
 for section in re.split(r'\n(?=Row: \d+ )',raw):
  m=re.fullmatch(r'Row: \d+ project_id=(.*?), config_content=(.*)',section,re.S)
  if m:rows.append({'project_id':m[1],'config_content':m[2]})
 if not rows:raise RuntimeError('未读到厂商配置，已保留原文，请检查备份目录：'+str(folder))
 (folder/'厂商配置.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
 (folder/'系统属性.txt').write_text(shell('getprop')+'\n')
 metadata={'created_at':datetime.datetime.now().astimezone().isoformat(),'target':config()['target'],'model':shell('getprop','ro.product.model'),'firmware':shell('getprop','ro.build.display.id'),'vendor_config_groups':len(rows),'scope':'Android设置、厂商配置、系统属性；不包含应用账号和应用数据'}
 (folder/'备份说明.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2))
 return {'message':f'已备份 {len(rows)} 组厂商配置和 Android 设置','path':str(folder),'count':len(rows)}
def main(action,args):
 if action=='status':
  ensure_connection();state=adb(['get-state'])
  if state!='device':raise RuntimeError('电视未连接：'+state)
  return {'message':'已连接 · '+shell('getprop','ro.product.model'),'target':config()['target'],'apps':apps()}
 if action=='connect':
  target=args[0].strip()
  if not re.fullmatch(r'(?:\d{1,3}\.){3}\d{1,3}:\d{1,5}',target):raise RuntimeError('请输入电视的 IP:端口，例如 192.0.2.10:5555')
  c=config();c['target']=target;CONFIG.write_text(json.dumps(c,ensure_ascii=False,indent=2));return main('status',[])
 if action=='apps':return {'message':'应用列表已刷新','apps':apps()}
 if action=='launch':
  component=args[0]
  if not re.fullmatch(r'[\w.$]+/[\w.$]+',component):raise RuntimeError('应用入口无效')
  output=shell('am','start','-n',component)
  if 'Error:' in output or 'Error type' in output:raise RuntimeError(output)
  return {'message':'应用已打开','detail':output}
 if action=='key':
  key=args[0]
  if key not in ['KEYCODE_DPAD_UP','KEYCODE_DPAD_DOWN','KEYCODE_DPAD_LEFT','KEYCODE_DPAD_RIGHT','KEYCODE_DPAD_CENTER','KEYCODE_HOME','KEYCODE_BACK','KEYCODE_VOLUME_UP','KEYCODE_VOLUME_DOWN','KEYCODE_VOLUME_MUTE']:raise RuntimeError('不支持的按键')
  shell('input','keyevent',key);return {'message':'已发送遥控按键'}
 if action=='screenshot':
  data=adb(['exec-out','screencap','-p'],binary=True)
  if not data.startswith(b'\x89PNG\r\n\x1a\n'):raise RuntimeError('电视未返回有效截图')
  folder=Path.home()/'Pictures/电视截图';folder.mkdir(parents=True,exist_ok=True)
  path=folder/(datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.png');path.write_bytes(data)
  return {'message':'电视截图已保存','path':str(path)}
 if action=='backup':return backup()
 if action=='install':
  path=Path(args[0])
  if path.suffix.lower()!='.apk' or not path.is_file():raise RuntimeError('请选择一个 APK 文件')
  temporary='/data/local/tmp/tv-console-'+uuid.uuid4().hex+'.apk'
  try:
   adb(['push',str(path),temporary],timeout=300)
   output=shell('pm','install','-r',temporary,timeout=180)
  finally:shell('rm','-f',temporary)
  if 'Success' not in output:raise RuntimeError(output)
  return {'message':'安装成功 · '+path.name,'detail':output,'apps':apps()}
 raise RuntimeError('未知操作：'+action)
if __name__=='__main__':
 try:print(json.dumps({'ok':True,**main(sys.argv[1],sys.argv[2:])},ensure_ascii=False))
 except Exception as error:print(json.dumps({'ok':False,'message':str(error)},ensure_ascii=False));sys.exit(1)
