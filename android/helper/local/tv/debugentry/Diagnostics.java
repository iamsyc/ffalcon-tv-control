package local.tv.debugentry;

import android.content.*;
import android.content.pm.*;
import android.hardware.usb.*;
import android.os.*;
import android.os.Process;
import android.provider.Settings;
import org.json.*;
import java.io.*;
import java.net.*;
import java.security.MessageDigest;
import java.util.*;

public final class Diagnostics {
    private final Context context;
    public volatile JSONObject snapshot;
    public volatile Map<String,List<File>> apkFiles=Collections.emptyMap();
    public volatile Map<String,ActivityInfo> activities=Collections.emptyMap();
    private final Map<String,JSONObject> probes=new LinkedHashMap<>();
    private final List<JSONObject> events=new ArrayList<>();
    public volatile String scanState="starting";
    public Diagnostics(Context context){this.context=context;}
    public static JSONObject error(String operation,Exception e){
        JSONObject j=new JSONObject();try{j.put("operation",operation).put("error",e.getClass().getSimpleName()).put("message",String.valueOf(e.getMessage()));}catch(JSONException ignored){}return j;
    }
    public synchronized void event(String operation,String result){
        try{events.add(new JSONObject().put("time_ms",System.currentTimeMillis()).put("operation",operation).put("result",result));if(events.size()>200)events.remove(0);}catch(JSONException ignored){}
        android.util.Log.i("TvDiagnostic",operation+": "+result);
    }
    public synchronized JSONArray events(){return new JSONArray(events);}
    public synchronized JSONObject probeResults(){return new JSONObject(probes);}
    public void probe(String name)throws InterruptedException{
        List<String> command=ReadProbes.COMMANDS.get(name);if(command==null)throw new IllegalArgumentException("Unknown fixed probe");
        JSONObject j;
        try{ReadProbes.Result r=ReadProbes.execute(command,6000);j=new JSONObject().put("command",new JSONArray(command)).put("uid",Process.myUid()).put("exit_code",r.exit).put("timed_out",r.timeout).put("truncated",r.truncated).put("duration_ms",r.millis).put("output",r.output);}
        catch(InterruptedException e){throw e;}
        catch(Exception e){j=error(name,e);}
        synchronized(this){probes.put(name,j);}event("probe "+name,"completed");
    }
    private static JSONObject component(ComponentInfo c)throws JSONException{
        return new JSONObject().put("name",c.name).put("exported",c.exported).put("enabled",c.enabled).put("process",c.processName);
    }
    public static String digest(byte[] bytes)throws Exception{
        byte[] value=MessageDigest.getInstance("SHA-256").digest(bytes);StringBuilder out=new StringBuilder();for(byte b:value)out.append(String.format(Locale.ROOT,"%02x",b&255));return out.toString();
    }
    public void scan()throws Exception{
        scanState="scanning";
        PackageManager pm=context.getPackageManager();JSONArray all=new JSONArray();
        Map<String,List<File>> files=new LinkedHashMap<>();Map<String,ActivityInfo> pages=new LinkedHashMap<>();
        int flags=PackageManager.GET_ACTIVITIES|PackageManager.GET_SERVICES|PackageManager.GET_RECEIVERS|PackageManager.GET_PROVIDERS|PackageManager.GET_PERMISSIONS|PackageManager.GET_SHARED_LIBRARY_FILES|PackageManager.GET_SIGNING_CERTIFICATES|PackageManager.MATCH_DISABLED_COMPONENTS;
        List<PackageInfo> packages=pm.getInstalledPackages(flags);packages.sort((a,b)->a.packageName.compareTo(b.packageName));
        for(PackageInfo p:packages){
            if(Thread.currentThread().isInterrupted())throw new InterruptedException("Diagnostic scan stopped");
            JSONObject item=new JSONObject().put("package",p.packageName).put("version",p.versionName).put("version_code",p.getLongVersionCode());
            ApplicationInfo app=p.applicationInfo;List<File> apks=new ArrayList<>();
            if(app!=null){
                item.put("label",String.valueOf(app.loadLabel(pm))).put("enabled",app.enabled).put("system",(app.flags&ApplicationInfo.FLAG_SYSTEM)!=0).put("debuggable",(app.flags&ApplicationInfo.FLAG_DEBUGGABLE)!=0).put("source",app.sourceDir).put("uid",app.uid);
                apks.add(new File(app.sourceDir));if(app.splitSourceDirs!=null)for(String path:app.splitSourceDirs)apks.add(new File(path));
                item.put("shared_libraries",app.sharedLibraryFiles==null?new JSONArray():new JSONArray(Arrays.asList(app.sharedLibraryFiles)));
            }
            JSONArray apkInfo=new JSONArray();for(int i=0;i<apks.size();i++){File f=apks.get(i);apkInfo.put(new JSONObject().put("index",i).put("name",f.getName()).put("size",f.length()).put("readable",f.isFile()&&f.canRead()));}item.put("apk_files",apkInfo);files.put(p.packageName,Collections.unmodifiableList(apks));
            JSONArray acts=new JSONArray();if(p.activities!=null)for(ActivityInfo a:p.activities){acts.put(component(a).put("permission",a.permission));pages.put(a.packageName+"/"+a.name,a);}item.put("activities",acts);
            JSONArray services=new JSONArray();if(p.services!=null)for(ServiceInfo s:p.services)services.put(component(s).put("permission",s.permission));item.put("services",services);
            JSONArray receivers=new JSONArray();if(p.receivers!=null)for(ActivityInfo a:p.receivers)receivers.put(component(a).put("permission",a.permission));item.put("receivers",receivers);
            JSONArray providers=new JSONArray();if(p.providers!=null)for(ProviderInfo a:p.providers)providers.put(component(a).put("authority",a.authority).put("read_permission",a.readPermission).put("write_permission",a.writePermission));item.put("providers",providers);
            JSONArray permissions=new JSONArray();if(p.requestedPermissions!=null)for(int i=0;i<p.requestedPermissions.length;i++)permissions.put(new JSONObject().put("name",p.requestedPermissions[i]).put("granted",p.requestedPermissionsFlags!=null&&(p.requestedPermissionsFlags[i]&PackageInfo.REQUESTED_PERMISSION_GRANTED)!=0));item.put("requested_permissions",permissions);
            JSONArray signers=new JSONArray();if(p.signingInfo!=null)for(Signature signature:p.signingInfo.getApkContentsSigners())signers.put(digest(signature.toByteArray()));item.put("signers_sha256",signers);all.put(item);
        }
        JSONObject selfPermissions=new JSONObject();for(String p:new String[]{"android.permission.DUMP","android.permission.WRITE_SECURE_SETTINGS","android.permission.MANAGE_DEBUGGING","android.permission.READ_LOGS","android.permission.QUERY_ALL_PACKAGES","android.permission.REQUEST_INSTALL_PACKAGES","android.permission.FOREGROUND_SERVICE_SPECIAL_USE"})selfPermissions.put(p,pm.checkPermission(p,context.getPackageName())==PackageManager.PERMISSION_GRANTED);
        JSONObject userRestrictions=new JSONObject();try{Bundle restrictions=context.getSystemService(UserManager.class).getUserRestrictions();for(String key:restrictions.keySet())userRestrictions.put(key,restrictions.getBoolean(key));}catch(SecurityException e){userRestrictions=error("user_restrictions",e);}
        JSONArray usb=new JSONArray();try{UsbManager manager=context.getSystemService(UsbManager.class);for(UsbDevice device:manager.getDeviceList().values()){JSONObject d=new JSONObject().put("vendor",device.getVendorId()).put("product",device.getProductId()).put("class",device.getDeviceClass()).put("interfaces",device.getInterfaceCount()).put("permission",manager.hasPermission(device));try{d.put("name",device.getProductName());}catch(SecurityException e){d.put("name","permission denied");}usb.put(d);}}catch(Exception e){usb.put(error("usb_devices",e));}
        JSONObject result=new JSONObject().put("diagnostic_version",9).put("captured_at_ms",System.currentTimeMillis()).put("app_uid",Process.myUid()).put("manufacturer",Build.MANUFACTURER).put("model",Build.MODEL).put("android",Build.VERSION.RELEASE).put("sdk",Build.VERSION.SDK_INT).put("security_patch",Build.VERSION.SECURITY_PATCH).put("display",Build.DISPLAY).put("fingerprint",Build.FINGERPRINT).put("hardware",Build.HARDWARE).put("soc",Build.SOC_MODEL).put("abis",new JSONArray(Arrays.asList(Build.SUPPORTED_ABIS))).put("self_permissions",selfPermissions).put("user_restrictions",userRestrictions).put("usb_host_devices",usb).put("settings",readSettings()).put("package_count",packages.size()).put("packages",all);
        apkFiles=Collections.unmodifiableMap(files);activities=Collections.unmodifiableMap(pages);snapshot=result;scanState="complete";event("inventory","packages="+packages.size());
    }
    public JSONObject readSettings()throws JSONException{
        JSONObject out=new JSONObject();String[] keys={"adb_enabled","adb_wifi_enabled","development_settings_enabled","verifier_verify_adb_installs","package_verifier_enable","install_non_market_apps","user_setup_complete","device_provisioned","accessibility_enabled","enabled_accessibility_services","adb_allowed_connection_time","package_verifier_user_consent"};
        for(String namespace:new String[]{"global","secure","system"}){JSONObject values=new JSONObject();for(String key:keys)try{String value=namespace.equals("global")?Settings.Global.getString(context.getContentResolver(),key):namespace.equals("secure")?Settings.Secure.getString(context.getContentResolver(),key):Settings.System.getString(context.getContentResolver(),key);values.put(key,value==null?JSONObject.NULL:value);}catch(SecurityException e){values.put(key,error("read "+key,e));}out.put(namespace,values);}return out;
    }
    public JSONArray candidatePages()throws JSONException{
        JSONArray out=new JSONArray();for(ActivityInfo a:activities.values()){
            String combined=(a.packageName+"/"+a.name).toLowerCase(Locale.ROOT);
            if(combined.matches(".*(setting|adb|debug|develop|factory|engineer|usb|wireless).*"))out.put(component(a).put("package",a.packageName).put("permission",a.permission).put("callable",callable(a)));
        }return out;
    }
    public boolean callable(ActivityInfo a){return a.exported&&a.enabled&&a.applicationInfo.enabled&&(a.permission==null||context.checkSelfPermission(a.permission)==PackageManager.PERMISSION_GRANTED);}
    public static List<String> addresses(){List<String> list=new ArrayList<>();try{Enumeration<NetworkInterface> interfaces=NetworkInterface.getNetworkInterfaces();while(interfaces.hasMoreElements()){Enumeration<InetAddress> addrs=interfaces.nextElement().getInetAddresses();while(addrs.hasMoreElements()){InetAddress a=addrs.nextElement();if(a instanceof Inet4Address&&a.isSiteLocalAddress())list.add(a.getHostAddress());}}}catch(SocketException ignored){}return list;}
    private static final String[] SYSTEM_ROOTS={"/system","/system_ext","/product","/vendor","/odm","/apex"};
    public File systemPath(String path,boolean directory)throws IOException{
        File f=new File(path).getCanonicalFile();String canonical=f.getPath();boolean allowed=false;for(String root:SYSTEM_ROOTS)if(canonical.equals(root)||canonical.startsWith(root+"/"))allowed=true;
        if(!allowed)throw new SecurityException("Only operating-system partitions are readable");
        if(directory){if(!f.isDirectory())throw new FileNotFoundException("Directory unavailable");}
        else if(!f.isFile())throw new FileNotFoundException("System file unavailable");
        return f;
    }
    public JSONArray systemList(String path)throws Exception{File[] children=systemPath(path,true).listFiles();if(children==null)throw new IOException("Directory is not readable");Arrays.sort(children,(a,b)->a.getName().compareTo(b.getName()));JSONArray out=new JSONArray();for(File f:children)out.put(new JSONObject().put("name",f.getName()).put("directory",f.isDirectory()).put("bytes",f.length()).put("readable",f.canRead()));return out;}
    public JSONObject usbSysfs(String path)throws Exception{
        String normalized=new File(path).getAbsoluteFile().toPath().normalize().toString();boolean allowed=false;
        for(String root:new String[]{"/sys/class/udc","/sys/class/android_usb","/sys/class/dual_role_usb","/sys/class/typec","/sys/kernel/config/usb_gadget"})if(normalized.equals(root)||normalized.startsWith(root+"/"))allowed=true;
        File file=new File(normalized).getCanonicalFile();if(!allowed||!file.getPath().startsWith("/sys/"))throw new SecurityException("Only USB controller and gadget sysfs entries are available");
        JSONObject result=new JSONObject().put("path",normalized).put("canonical",file.getPath()).put("exists",file.exists()).put("readable",file.canRead());
        if(file.isDirectory()){File[] children=file.listFiles();if(children==null)throw new IOException("USB directory is not readable");JSONArray names=new JSONArray();for(File child:children)names.put(new JSONObject().put("name",child.getName()).put("directory",child.isDirectory()));return result.put("children",names);}
        try(InputStream input=new FileInputStream(file);ByteArrayOutputStream out=new ByteArrayOutputStream()){byte[] bytes=new byte[4096];int n;while(out.size()<65536&&(n=input.read(bytes,0,Math.min(bytes.length,65536-out.size())))!=-1)out.write(bytes,0,n);return result.put("text",out.toString("UTF-8")).put("limit_bytes",65536);}
    }
}
