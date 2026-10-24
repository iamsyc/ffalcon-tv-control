#!/usr/bin/env python3
"""Device regression: desktop wheel enters and releases native fling; other apps keep SDK scrolling."""
import argparse,json,pathlib,struct,time
from probe_scroll import Control,run,snapshot
p=argparse.ArgumentParser();p.add_argument('server');p.add_argument('--output',required=True);a=p.parse_args()
report={}
run('shell','input keyevent KEYCODE_HOME')
before=snapshot();log=a.output+'.desktop.log';control=Control(a.server,log)
try:
 for i in range(42):control.scroll(1000,800,-0.12);time.sleep(1/60)
 time.sleep(.3)
finally:control.close()
after=snapshot();events=pathlib.Path(log).read_text()
downs=events.count('TV desktop wheel: down');ups=events.count('TV desktop wheel: up')
report['desktop']={'down':downs,'up':ups,'repeat':events.count('TV desktop wheel: repeat'),'native_animation':downs>0 and ups==downs and 'TV desktop wheel: repeat' in events,'spatial_change':[(n['id'],n['bounds'],n['focused']) for n in before]!=[(n['id'],n['bounds'],n['focused']) for n in after]}
run('shell','am start -n local.tv.debugentry/.MainActivity')
run('shell','input swipe 1860 200 1860 900 400');time.sleep(.3)
before=snapshot();log=a.output+'.helper.log';control=Control(a.server,log)
try:
 for i in range(30):control.scroll(1000,800,-0.12);time.sleep(1/60)
 time.sleep(.3)
finally:control.close()
after=snapshot();events=pathlib.Path(log).read_text()
report['helper']={'desktop_route_used':'TV desktop wheel:' in events,'content_moved':[(n['text'],n['bounds']) for n in before]!=[(n['text'],n['bounds']) for n in after]}
run('shell','input keyevent KEYCODE_HOME')
log=a.output+'.disconnect.log';control=Control(a.server,log)
try:
 for i in range(15):control.scroll(1000,800,0.12);time.sleep(1/60)
finally:control.close()
events=pathlib.Path(log).read_text();downs=events.count('TV desktop wheel: down');ups=events.count('TV desktop wheel: up')
report['disconnect']={'down':downs,'up':ups,'released':downs>0 and downs==ups}
report['passed']=report['desktop']['native_animation'] and report['desktop']['spatial_change'] and not report['helper']['desktop_route_used'] and report['helper']['content_moved'] and report['disconnect']['released']
pathlib.Path(a.output).write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False,indent=2))
raise SystemExit(0 if report['passed'] else 1)
