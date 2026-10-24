package local.tv.debugentry;

import android.app.Activity;
import android.content.*;
import android.net.Uri;
import android.os.*;
import android.provider.Settings;
import android.widget.*;
import android.view.ViewGroup;
import java.lang.ref.WeakReference;

public class MainActivity extends Activity {
    private static WeakReference<MainActivity> active=new WeakReference<>(null);
    public static volatile Intent pendingInstall;
    private final Handler handler=new Handler(Looper.getMainLooper());
    private LinearLayout panel;private TextView status,actionStatus;private Switch control;
    private boolean visible;
    public static MainActivity visible(){MainActivity a=active.get();return a!=null&&a.visible?a:null;}
    private int dp(int n){return(int)(n*getResources().getDisplayMetrics().density+.5f);}
    private void text(String s,int size){TextView t=new TextView(this);t.setText(s);t.setTextSize(size);t.setPadding(0,dp(8),0,dp(8));panel.addView(t);}
    private void button(String title,Runnable action){Button b=new Button(this);b.setText(title);b.setTextSize(17);LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,dp(60));lp.setMargins(0,dp(5),0,dp(5));panel.addView(b,lp);b.setOnClickListener(v->{try{action.run();}catch(Exception e){actionStatus.setText("操作未完成："+e.toString());}});}
    @Override public void onCreate(Bundle b){super.onCreate(b);ScrollView scroll=new ScrollView(this);panel=new LinearLayout(this);panel.setOrientation(LinearLayout.VERTICAL);panel.setPadding(dp(40),dp(20),dp(40),dp(20));scroll.addView(panel);setContentView(scroll);
        text("电视调试诊断 v9",28);
        text("Android "+Build.VERSION.RELEASE+" / "+Build.MODEL+" / 安全补丁 "+Build.VERSION.SECURITY_PATCH,17);
        text("自动采集应用、组件、权限、调试属性、USB状态和读取限制。局域网访问带随机凭据，不向互联网发送数据，不读取账号、用户文件或应用私有数据。切换到系统设置后服务仍运行，可在本页停止。",17);
        status=new TextView(this);status.setTextSize(18);status.setPadding(0,dp(10),0,dp(10));status.setText("正在启动诊断服务…");panel.addView(status);
        actionStatus=new TextView(this);actionStatus.setTextSize(16);actionStatus.setPadding(0,dp(6),0,dp(6));panel.addView(actionStatus);
        control=new Switch(this);control.setText("允许电脑操作设置和运行本工具权限内的命令");control.setTextSize(18);control.setPadding(0,dp(12),0,dp(12));panel.addView(control);
        control.setOnCheckedChangeListener((v,enabled)->{HubService h=HubService.current;if(h!=null){h.allowPageControl=enabled;h.data.event("owner_page_control",String.valueOf(enabled));}else if(enabled){control.setChecked(false);status.setText("请先启动诊断服务");}});
        button("开始 / 刷新全部只读诊断",()->start("refresh"));
        button("可选：打开无障碍授权页面",()->openSettings(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)));
        text("无障碍功能仅在你通过系统页面手动开启后可用，供读取当前电视屏幕、截图和遥控操作。自动采集不依赖此授权。",15);
        button("可选：允许此工具接收局域网更新",()->openSettings(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,Uri.parse("package:"+getPackageName()))));
        text("后续更新只接受本工具同签名且版本更高的 APK，最终仍由电视标准安装页面确认。厂家安装策略仍可能拦截。",15);
        button("显示待确认的工具更新",this::showPendingInstall);
        button("停止局域网诊断",()->{HubService h=HubService.current;if(h!=null)h.stopSelf();control.setChecked(false);status.setText("局域网诊断已停止");});
        start("start");
    }
    private void start(String action){startForegroundService(new Intent(this,HubService.class).setAction(action));}
    private void openSettings(Intent intent){try{startActivity(intent);}catch(ActivityNotFoundException|SecurityException e){actionStatus.setText("系统未开放这个标准入口。可继续读取报告寻找雷鸟自有入口。\n"+e.getClass().getSimpleName());}}
    public void showPendingInstall(){Intent intent=pendingInstall;if(intent==null){actionStatus.setText("当前没有待确认的更新");return;}try{startActivity(intent);pendingInstall=null;}catch(ActivityNotFoundException|SecurityException e){actionStatus.setText("无法打开更新确认页："+e);}}
    private final Runnable updateStatus=new Runnable(){@Override public void run(){if(!visible)return;HubService h=HubService.current;
        if(h==null)status.setText("局域网诊断已停止");
        else status.setText("局域网诊断："+Diagnostics.addresses()+":"+HubService.PORT+"\n电脑访问路径："+h.accessPath()+"report\n采集："+h.data.scanState+"；服务："+h.state+"\n界面控制："+(h.allowPageControl?"已允许":"未允许")+"；无障碍："+(UiAccess.current!=null?"已连接":"未开启")+"\n你可以切换到电视设置；停止按钮可关闭局域网服务。");
        handler.postDelayed(this,2000);
    }};
    @Override protected void onResume(){super.onResume();visible=true;active=new WeakReference<>(this);HubService h=HubService.current;if(h!=null)control.setChecked(h.allowPageControl);handler.post(updateStatus);}
    @Override protected void onPause(){visible=false;handler.removeCallbacks(updateStatus);super.onPause();}
}
