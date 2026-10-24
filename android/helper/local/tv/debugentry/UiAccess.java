package local.tv.debugentry;

import android.accessibilityservice.AccessibilityService;
import android.graphics.*;
import android.hardware.HardwareBuffer;
import android.os.Bundle;
import android.view.Display;
import android.view.accessibility.*;
import org.json.*;
import java.io.ByteArrayOutputStream;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;

/** Optional. Android requires the owner to enable this service in system settings. */
public class UiAccess extends AccessibilityService {
    public static volatile UiAccess current;
    @Override protected void onServiceConnected(){current=this;}
    @Override public void onAccessibilityEvent(AccessibilityEvent event){}
    @Override public void onInterrupt(){}
    @Override public void onDestroy(){if(current==this)current=null;super.onDestroy();}
    public JSONObject tree()throws Exception{
        AccessibilityNodeInfo root=getRootInActiveWindow();
        if(root==null)return new JSONObject().put("available",false);
        return new JSONObject().put("available",true).put("captured_at_ms",System.currentTimeMillis()).put("root",node(root,"0",0,new int[]{0}));
    }
    private JSONObject node(AccessibilityNodeInfo n,String path,int depth,int[] count)throws JSONException{
        JSONObject j=new JSONObject().put("path",path).put("package",String.valueOf(n.getPackageName())).put("class",String.valueOf(n.getClassName())).put("view_id",n.getViewIdResourceName()).put("text",String.valueOf(n.getText())).put("description",String.valueOf(n.getContentDescription())).put("clickable",n.isClickable()).put("enabled",n.isEnabled()).put("focused",n.isFocused()).put("scrollable",n.isScrollable());
        Rect r=new Rect();n.getBoundsInScreen(r);j.put("bounds",new JSONArray(new int[]{r.left,r.top,r.right,r.bottom}));
        JSONArray children=new JSONArray();if(depth<32&&++count[0]<2000)for(int i=0;i<n.getChildCount();i++){AccessibilityNodeInfo c=n.getChild(i);if(c!=null)children.put(node(c,path+"."+i,depth+1,count));}return j.put("children",children);
    }
    public JSONObject act(JSONObject request)throws Exception{
        String action=request.getString("action");boolean result;
        if(action.equals("back"))result=performGlobalAction(GLOBAL_ACTION_BACK);
        else if(action.equals("home"))result=performGlobalAction(GLOBAL_ACTION_HOME);
        else{
            AccessibilityNodeInfo n=getRootInActiveWindow();String path=request.getString("path");if(!path.matches("0(\\.\\d+)*"))throw new IllegalArgumentException("Invalid node path");String[] parts=path.split("\\.");
            for(int i=1;i<parts.length&&n!=null;i++)n=n.getChild(Integer.parseInt(parts[i]));if(n==null)throw new IllegalArgumentException("Node no longer exists; read tree again");
            String expected=request.optString("expected_text",null);if(expected!=null&&!expected.equals(String.valueOf(n.getText())))throw new IllegalArgumentException("Screen changed; read tree again");
            if(action.equals("click"))result=n.performAction(AccessibilityNodeInfo.ACTION_CLICK);
            else if(action.equals("focus"))result=n.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
            else if(action.equals("scroll_forward"))result=n.performAction(AccessibilityNodeInfo.ACTION_SCROLL_FORWARD);
            else if(action.equals("scroll_backward"))result=n.performAction(AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD);
            else if(action.equals("text")){Bundle args=new Bundle();args.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE,request.getString("text"));result=n.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT,args);}
            else throw new IllegalArgumentException("Unsupported UI action");
        }
        return new JSONObject().put("action",action).put("accepted",result).put("requires_screen_readback",true);
    }
    public byte[] screenshot()throws Exception{
        CountDownLatch ready=new CountDownLatch(1);AtomicReference<byte[]> result=new AtomicReference<>();AtomicReference<Exception> failure=new AtomicReference<>();
        takeScreenshot(Display.DEFAULT_DISPLAY,getMainExecutor(),new TakeScreenshotCallback(){
            @Override public void onSuccess(ScreenshotResult screenshot){try(HardwareBuffer buffer=screenshot.getHardwareBuffer()){
                Bitmap hardware=Bitmap.wrapHardwareBuffer(buffer,screenshot.getColorSpace());if(hardware==null)throw new IllegalStateException("Cannot wrap screenshot buffer");
                Bitmap copy=hardware.copy(Bitmap.Config.ARGB_8888,false);hardware.recycle();ByteArrayOutputStream out=new ByteArrayOutputStream();copy.compress(Bitmap.CompressFormat.PNG,100,out);copy.recycle();result.set(out.toByteArray());
            }catch(Exception e){failure.set(e);}finally{ready.countDown();}}
            @Override public void onFailure(int code){failure.set(new IllegalStateException("Android screenshot error "+code));ready.countDown();}
        });
        if(!ready.await(6,TimeUnit.SECONDS))throw new TimeoutException("Screenshot timed out");if(failure.get()!=null)throw failure.get();return result.get();
    }
}
