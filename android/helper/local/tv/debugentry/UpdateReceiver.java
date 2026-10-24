package local.tv.debugentry;
import android.content.*;
import android.content.pm.PackageInstaller;
import org.json.JSONObject;

public class UpdateReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context context,Intent intent){
        int status=intent.getIntExtra(PackageInstaller.EXTRA_STATUS,PackageInstaller.STATUS_FAILURE);
        String message=intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE);
        HubService hub=HubService.current;
        if(hub!=null)hub.data.event("self_update_status",status+": "+String.valueOf(message));
        if(status==PackageInstaller.STATUS_PENDING_USER_ACTION){
            Intent confirmation=intent.getParcelableExtra(Intent.EXTRA_INTENT,Intent.class);
            MainActivity.pendingInstall=confirmation;
            MainActivity activity=MainActivity.visible();
            if(activity!=null)activity.showPendingInstall();
        }
    }
}
