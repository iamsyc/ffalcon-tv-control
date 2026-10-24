package local.tv.debugentry;

import android.app.*;
import android.content.*;
import android.content.pm.*;
import android.net.Uri;
import android.database.Cursor;
import android.os.*;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;

public class HubService extends Service {
    public static final int PORT=8765;
    public static volatile HubService current;
    public volatile boolean allowPageControl=false;
    public volatile String state="starting";
    public Diagnostics data;
    private LocalServer server;
    private volatile AdbBridge adbBridge;
    private VendorAdbProbe vendorAdb;
    private final ExecutorService scans=Executors.newSingleThreadExecutor();
    private final Handler main=new Handler(Looper.getMainLooper());
    private volatile boolean scanBusy;
    private String token;
    private static final String CHANNEL="local_tv_diagnostics";
    @Override public void onCreate(){
        super.onCreate();current=this;data=new Diagnostics(this);vendorAdb=new VendorAdbProbe(this);
        SharedPreferences preferences=getSharedPreferences("diagnostic",MODE_PRIVATE);
        token=preferences.getString("lan_token",null);
        if(token==null){token=UUID.randomUUID().toString().replace("-","");preferences.edit().putString("lan_token",token).apply();}
    }
    public String accessPath(){return "/"+token+"/";}
    @Override public int onStartCommand(Intent intent,int flags,int startId){
        if(intent!=null&&"stop".equals(intent.getAction())){stopSelf();return START_NOT_STICKY;}
        if(server==null){
            NotificationManager manager=getSystemService(NotificationManager.class);manager.createNotificationChannel(new NotificationChannel(CHANNEL,"局域网电视诊断",NotificationManager.IMPORTANCE_LOW));
            PendingIntent show=PendingIntent.getActivity(this,1,new Intent(this,MainActivity.class),PendingIntent.FLAG_IMMUTABLE|PendingIntent.FLAG_UPDATE_CURRENT);
            PendingIntent stop=PendingIntent.getService(this,2,new Intent(this,HubService.class).setAction("stop"),PendingIntent.FLAG_IMMUTABLE|PendingIntent.FLAG_UPDATE_CURRENT);
            Notification notice=new Notification.Builder(this,CHANNEL).setSmallIcon(R.drawable.ic_debug).setContentTitle("局域网电视诊断运行中").setContentText("点击返回工具；可随时停止").setContentIntent(show).setOngoing(true).addAction(new Notification.Action.Builder(null,"停止诊断",stop).build()).build();
            startForeground(87,notice,ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
            try{server=new LocalServer(PORT,token,this::route);server.start();state="listening";data.event("local_server","started on port "+PORT);refresh(true);}
            catch(IOException e){state=e.toString();data.event("local_server",state);stopSelf();}
        }else if(intent!=null&&"refresh".equals(intent.getAction()))refresh(true);
        return START_NOT_STICKY;
    }
    public synchronized boolean refresh(boolean probes){
        if(scanBusy)return false;scanBusy=true;
        scans.execute(()->{try{data.scan();if(probes)for(String name:ReadProbes.COMMANDS.keySet())data.probe(name);}catch(InterruptedException e){Thread.currentThread().interrupt();data.scanState="stopped";}catch(Exception e){data.scanState="failed: "+e;data.event("inventory_error",e.toString());}finally{scanBusy=false;}});return true;
    }
    @Override public IBinder onBind(Intent intent){return null;}
    @Override public void onDestroy(){allowPageControl=false;if(server!=null)server.close();if(adbBridge!=null)adbBridge.close();scans.shutdownNow();if(current==this)current=null;stopForeground(STOP_FOREGROUND_REMOVE);super.onDestroy();}
    public JSONObject status()throws JSONException{
        PackageManager pm=getPackageManager();return new JSONObject().put("version",9).put("state",state).put("scan",data.scanState).put("scan_busy",scanBusy).put("addresses",new JSONArray(Diagnostics.addresses())).put("port",PORT).put("adb_bridge_target",adbBridge==null?JSONObject.NULL:adbBridge.targetPort).put("page_control",allowPageControl).put("accessibility_connected",UiAccess.current!=null).put("unknown_source_allowed",pm.canRequestPackageInstalls()).put("activity_visible",MainActivity.visible()!=null).put("report_ready",data.snapshot!=null);
    }
    private LocalServer.Response json(int code,Object value){return LocalServer.Response.json(code,String.valueOf(value));}
    private JSONObject ok(String message)throws JSONException{return new JSONObject().put("message",message);}
    private LocalServer.Response route(LocalServer.Request r)throws Exception{
        try{
            if(r.method.equals("GET"))switch(r.route){
                case "status":return json(200,status());
                case "vendor-adb":return json(200,vendorAdb.inspect());
                case "vendor-adb-result":return json(200,vendorAdb.result());
                case "local-adb":{
                    AdbProbe.Result result=AdbProbe.connect(Integer.parseInt(r.query.getOrDefault("port","5555")));
                    return json(200,new JSONObject().put("port",result.port).put("state",result.state).put("detail",result.detail));
                }
                case "capabilities":return json(200,new JSONObject().put("read",new JSONArray(Arrays.asList("status","vendor-adb","vendor-adb-result","local-adb?port=5555","report","probes","events","settings","pages","resolve?action=...","permission?name=...","apk?package=...&index=0","system-list?path=...","system-file?path=...","ui-tree","screenshot"))).put("post",new JSONArray(Arrays.asList("command (argument list; application UID; TV toggle required)","query (read content provider; application UID; TV toggle required)","provider (update/call; application UID; TV toggle required)","vendor-adb (identity, pair, stop-pairing; TV toggle + visible tool required)","local-adb-bridge (TV toggle + visible tool required)","refresh","probe (fixed name only)","open (exported activity; TV toggle required)","ui (accessibility + TV toggle required)","update (same package/signature; Android confirmation)","stop"))).put("fixed_probes",new JSONArray(ReadProbes.COMMANDS.keySet())).put("status",status()));
                case "report":return data.snapshot==null?json(data.scanState.startsWith("failed")?500:202,ok(data.scanState)):json(200,data.snapshot);
                case "probes":return json(200,data.probeResults());
                case "events":return json(200,data.events());
                case "settings":return json(200,data.readSettings());
                case "pages":return json(200,data.candidatePages());
                case "resolve":{
                    Intent query=new Intent(required(r,"action"));if(r.query.containsKey("package"))query.setPackage(r.query.get("package"));if(r.query.containsKey("data"))query.setData(Uri.parse(r.query.get("data")));
                    JSONArray matches=new JSONArray();for(ResolveInfo result:getPackageManager().queryIntentActivities(query,PackageManager.MATCH_DISABLED_COMPONENTS|PackageManager.GET_RESOLVED_FILTER)){
                        ActivityInfo a=result.activityInfo;JSONObject page=new JSONObject().put("component",a.packageName+"/"+a.name).put("callable",data.callable(a)).put("permission",a.permission);JSONArray actions=new JSONArray();if(result.filter!=null)for(int i=0;i<result.filter.countActions();i++)actions.put(result.filter.getAction(i));matches.put(page.put("actions",actions));
                    }return json(200,matches);
                }
                case "permission":{String name=required(r,"name");PermissionInfo p=getPackageManager().getPermissionInfo(name,0);return json(200,new JSONObject().put("name",p.name).put("owner_package",p.packageName).put("protection_level",p.protectionLevel).put("granted_to_tool",checkSelfPermission(name)==PackageManager.PERMISSION_GRANTED));}
                case "apk":{
                    String name=r.query.get("package");List<File> files=data.apkFiles.get(name);int index=Integer.parseInt(r.query.getOrDefault("index","0"));
                    if(files==null||index<0||index>=files.size())return json(404,ok("installed APK not found"));File file=files.get(index);if(!file.isFile()||!file.canRead())return json(403,ok("APK is not readable by this application"));
                    return LocalServer.Response.file(file,"application/vnd.android.package-archive");
                }
                case "system-list":return json(200,data.systemList(required(r,"path")));
                case "usb-sysfs":return json(200,data.usbSysfs(required(r,"path")));
                case "system-file":{File file=data.systemPath(required(r,"path"),false);if(!file.isFile()||!file.canRead())return json(403,ok("system code file is not readable"));return LocalServer.Response.file(file,"application/octet-stream");}
                case "ui-tree":{UiAccess ui=UiAccess.current;if(ui==null)return json(409,ok("owner must enable accessibility service in TV settings"));return json(200,ui.tree());}
                case "screenshot":{UiAccess ui=UiAccess.current;if(ui==null)return json(409,ok("owner must enable accessibility service in TV settings"));return LocalServer.Response.bytes("image/png",ui.screenshot());}
                default:return json(404,ok("unknown read endpoint"));
            }
            if(r.method.equals("POST"))switch(r.route){
                case "refresh":return json(202,ok(refresh(true)?"refresh started":"refresh already running"));
                case "probe":{
                    JSONObject request=new JSONObject(r.text());String name=request.getString("name");if(!ReadProbes.COMMANDS.containsKey(name))return json(400,ok("unknown fixed probe; arbitrary commands are not supported"));
                    data.probe(name);return json(200,data.probeResults().get(name));
                }
                case "open":{if(!allowPageControl)return json(403,ok("enable page control on TV first"));return json(200,openPage(new JSONObject(r.text())));}
                case "ui":{if(!allowPageControl)return json(403,ok("enable page control on TV first"));UiAccess ui=UiAccess.current;if(ui==null)return json(409,ok("accessibility is not enabled"));JSONObject request=new JSONObject(r.text());return json(200,onMain(()->ui.act(request)));}
                case "update":return json(202,installUpdate(r.body));
                case "command":{
                    if(!allowPageControl)throw new SecurityException("Enable computer control on TV first");
                    JSONArray input=new JSONObject(r.text()).getJSONArray("args");
                    if(input.length()==0)throw new IllegalArgumentException("Command arguments are empty");
                    List<String> args=new ArrayList<>();for(int i=0;i<input.length();i++)args.add(input.getString(i));
                    ReadProbes.Result result=ReadProbes.execute(args,10000);
                    return json(200,new JSONObject().put("uid",android.os.Process.myUid()).put("output",result.output).put("exit_code",result.exit).put("timed_out",result.timeout).put("truncated",result.truncated).put("duration_ms",result.millis));
                }
                case "provider":{
                    if(!allowPageControl)throw new SecurityException("Enable computer control on TV first");
                    return json(200,ProviderCommands.execute(this,new JSONObject(r.text())));
                }
                case "query":{
                    if(!allowPageControl)throw new SecurityException("Enable computer control on TV first");
                    JSONObject request=new JSONObject(r.text());Uri uri=Uri.parse(request.getString("uri"));
                    if(!"content".equals(uri.getScheme()))throw new IllegalArgumentException("Use a content URI");
                    JSONArray input=request.optJSONArray("columns");String[] columns=null;
                    if(input!=null){columns=new String[input.length()];for(int i=0;i<columns.length;i++)columns[i]=input.getString(i);}
                    JSONArray rows=new JSONArray();
                    try(Cursor cursor=getContentResolver().query(uri,columns,null,null,null)){
                        if(cursor!=null)while(cursor.moveToNext()){
                            JSONObject row=new JSONObject();for(int i=0;i<cursor.getColumnCount();i++)row.put(cursor.getColumnName(i),cursor.isNull(i)?JSONObject.NULL:cursor.getString(i));rows.put(row);
                        }
                    }
                    return json(200,new JSONObject().put("uid",android.os.Process.myUid()).put("rows",rows));
                }
                case "vendor-adb":{
                    if(!allowPageControl||MainActivity.visible()==null)throw new SecurityException("Open the tool and enable page control on TV first");
                    JSONObject request=new JSONObject(r.text());
                    return json(200,vendorAdb.execute(request.getString("operation"),request.optString("service_name"),request.optString("password")));
                }
                case "local-adb-bridge":{
                    if(!allowPageControl||MainActivity.visible()==null)throw new SecurityException("Open the tool and enable page control on TV first");
                    int port=new JSONObject(r.text()).optInt("port",5555);AdbProbe.Result check=AdbProbe.connect(port);
                    if(!check.state.equals("auth_required")&&!check.state.equals("connected"))return json(409,ok(check.state+": "+check.detail));
                    return json(200,onMain(()->{
                        if(adbBridge==null){adbBridge=new AdbBridge(port);adbBridge.start();}
                        if(adbBridge.targetPort!=port)throw new IllegalArgumentException("Stop diagnostics before changing the bridge target");
                        return new JSONObject().put("bridge_port",AdbBridge.PORT).put("target_port",port).put("message","Connect the computer using normal adb; Android still handles authorization");
                    }));
                }
                case "stop":main.postDelayed(this::stopSelf,250);return json(200,ok("stopping local diagnostics"));
                default:return json(404,ok("unknown action endpoint"));
            }
            return json(405,ok("unsupported method"));
        }catch(SecurityException e){data.event(r.route,e.toString());return json(403,Diagnostics.error(r.route,e));}
        catch(IllegalArgumentException|JSONException e){data.event(r.route,e.toString());return json(400,Diagnostics.error(r.route,e));}
        catch(Exception e){data.event(r.route,e.toString());return json(500,Diagnostics.error(r.route,e));}
    }
    private String required(LocalServer.Request r,String key){String value=r.query.get(key);if(value==null||value.isEmpty())throw new IllegalArgumentException("Missing "+key);return value;}
    private <T>T onMain(Callable<T> action)throws Exception{
        FutureTask<T> task=new FutureTask<>(()->{
            if(current!=this||!allowPageControl)throw new SecurityException("Page control is no longer enabled");
            return action.call();
        });
        main.post(task);
        try{return task.get(5,TimeUnit.SECONDS);}
        finally{task.cancel(false);main.removeCallbacks(task);}
    }
    private JSONObject openPage(JSONObject request)throws Exception{
        if(MainActivity.visible()==null&&UiAccess.current==null)throw new IllegalArgumentException("Return to the diagnostic tool before opening another page, or enable its optional accessibility service");
        String name=request.getString("component");ComponentName component=ComponentName.unflattenFromString(name);if(component==null)throw new IllegalArgumentException("Use package/full.activity.Name");
        ActivityInfo activity=getPackageManager().getActivityInfo(component,PackageManager.MATCH_DISABLED_COMPONENTS);
        if(!data.callable(activity))throw new SecurityException("Activity is disabled, private or requires an unavailable permission");
        String lower=(component.flattenToString()+" "+request.optString("action")).toLowerCase(Locale.ROOT);
        if(lower.matches(".*(master_clear|factory.?reset|wipe|erase|format|recovery|shutdown|reboot|poweroff).*"))throw new SecurityException("Destructive system actions are not exposed by this diagnostic tool");
        if(!component.getPackageName().matches("(?i).*(setting|factory|engineer|develop|debug|adb|permission|packageinstaller).*"))throw new SecurityException("Only system settings, permission and diagnostic pages can be opened");
        Intent intent=new Intent().setComponent(component).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        if(request.has("action"))intent.setAction(request.getString("action"));
        if(request.has("data")){Uri uri=Uri.parse(request.getString("data"));if(uri.getScheme()!=null&&!Arrays.asList("package","android-app").contains(uri.getScheme()))throw new SecurityException("Only package settings URI data is supported");intent.setData(uri);}
        JSONObject extras=request.optJSONObject("extras");if(extras!=null)intent.putExtras(intentExtras(extras,0));
        onMain(()->{startActivity(intent);return true;});data.event("open_page",component.flattenToString());
        return new JSONObject().put("request_sent",true).put("component",component.flattenToString()).put("requires_screen_readback",true);
    }
    private Bundle intentExtras(JSONObject values,int depth)throws JSONException{
        if(depth>6)throw new IllegalArgumentException("Intent extras are nested too deeply");Bundle out=new Bundle();
        for(Iterator<String> keys=values.keys();keys.hasNext();){String key=keys.next();Object value=values.get(key);
            if(value instanceof Boolean)out.putBoolean(key,(Boolean)value);else if(value instanceof Integer)out.putInt(key,(Integer)value);else if(value instanceof Long)out.putLong(key,(Long)value);else if(value instanceof String)out.putString(key,(String)value);
            else if(value instanceof JSONObject){JSONObject typed=(JSONObject)value;String type=typed.getString("type");if(type.equals("component")){ComponentName c=ComponentName.unflattenFromString(typed.getString("value"));if(c==null)throw new IllegalArgumentException("Invalid component extra");out.putParcelable(key,c);}else if(type.equals("bundle"))out.putBundle(key,intentExtras(typed.getJSONObject("value"),depth+1));else throw new IllegalArgumentException("Unsupported typed extra");}
            else throw new IllegalArgumentException("Unsupported intent extra");
        }return out;
    }
    private JSONObject installUpdate(byte[] bytes)throws Exception{
        if(MainActivity.visible()==null)throw new IllegalArgumentException("Open the diagnostic tool on TV before an update");
        if(!getPackageManager().canRequestPackageInstalls())throw new SecurityException("Allow this diagnostic tool to install updates in TV system settings first");
        if(bytes.length==0)throw new IllegalArgumentException("APK body is empty");
        File file=File.createTempFile("incoming-update-",".apk",getCacheDir());
        try{
            try(OutputStream out=new FileOutputStream(file)){out.write(bytes);}
            PackageManager pm=getPackageManager();PackageInfo incoming=pm.getPackageArchiveInfo(file.getPath(),PackageManager.GET_SIGNING_CERTIFICATES);PackageInfo installed=pm.getPackageInfo(getPackageName(),PackageManager.GET_SIGNING_CERTIFICATES);
            if(incoming==null||!getPackageName().equals(incoming.packageName))throw new SecurityException("Only updates to this diagnostic package are accepted");
            if(incoming.getLongVersionCode()<=installed.getLongVersionCode())throw new SecurityException("Update must have a higher version code");
            Signature[] old=installed.signingInfo.getApkContentsSigners(),next=incoming.signingInfo==null?new Signature[0]:incoming.signingInfo.getApkContentsSigners();
            if(old.length!=1||next.length!=1||!Arrays.equals(old[0].toByteArray(),next[0].toByteArray()))throw new SecurityException("Update signature does not match the installed tool");
            PackageInstaller installer=pm.getPackageInstaller();PackageInstaller.SessionParams params=new PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL);params.setAppPackageName(getPackageName());params.setSize(bytes.length);params.setRequireUserAction(PackageInstaller.SessionParams.USER_ACTION_REQUIRED);int sessionId=installer.createSession(params);
            try(PackageInstaller.Session session=installer.openSession(sessionId)){
                try(OutputStream out=session.openWrite("base.apk",0,bytes.length)){out.write(bytes);session.fsync(out);}
                Intent callback=new Intent(this,UpdateReceiver.class).setAction("local.tv.debugentry.UPDATE_RESULT");PendingIntent result=PendingIntent.getBroadcast(this,sessionId,callback,PendingIntent.FLAG_MUTABLE|PendingIntent.FLAG_UPDATE_CURRENT);session.commit(result.getIntentSender());
            }
            data.event("self_update","staged version "+incoming.getLongVersionCode()+", session "+sessionId);
            return new JSONObject().put("staged",true).put("version_code",incoming.getLongVersionCode()).put("session",sessionId).put("requires_android_confirmation",true);
        }finally{file.delete();}
    }
}
