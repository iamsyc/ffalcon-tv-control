from pathlib import Path
import os,subprocess,tempfile
root=Path(__file__).resolve().parents[1]
android=Path(os.environ['ANDROID_HOME'])/'platforms/android-35/android.jar'
with tempfile.TemporaryDirectory(prefix='tv-socket-lifecycle-') as tmp:
 out=Path(tmp)
 source=root/'local/tv/debugentry'
 subprocess.run(['javac','-cp',str(android),'-d',str(out),*[str(p) for p in (root/'tests').rglob('*.java')],str(source/'VendorAdbProbe.java'),str(source/'VendorAdbCommands.java')],check=True)
 subprocess.run(['java','-cp',str(out)+os.pathsep+str(android),'SocketLifecycleCheck'],check=True)
