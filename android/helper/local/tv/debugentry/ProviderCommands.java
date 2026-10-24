package local.tv.debugentry;

import android.content.ContentValues;
import android.content.Context;
import android.net.Uri;
import android.os.Bundle;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.Iterator;

/** Runs owner-requested content-provider operations with the application's existing UID. */
public final class ProviderCommands {
    public static JSONObject execute(Context context,JSONObject request)throws Exception{
        Uri uri=Uri.parse(request.getString("uri"));
        if(!"content".equals(uri.getScheme()))throw new IllegalArgumentException("Use a content URI");
        String operation=request.getString("operation");
        JSONObject response=new JSONObject().put("uid",android.os.Process.myUid());
        if(operation.equals("update")){
            JSONObject input=request.getJSONObject("values");ContentValues values=new ContentValues();
            for(Iterator<String> keys=input.keys();keys.hasNext();){
                String key=keys.next();Object value=input.get(key);
                if(value==JSONObject.NULL)values.putNull(key);
                else if(value instanceof Boolean)values.put(key,(Boolean)value);
                else if(value instanceof Number)values.put(key,value.toString());
                else values.put(key,(String)value);
            }
            JSONArray supplied=request.optJSONArray("selection_args");String[] args=null;
            if(supplied!=null){args=new String[supplied.length()];for(int i=0;i<args.length;i++)args[i]=supplied.getString(i);}
            String selection=request.isNull("selection")?null:request.optString("selection",null);
            return response.put("updated",context.getContentResolver().update(uri,values,selection,args));
        }
        if(operation.equals("call")){
            Bundle extras=new Bundle();JSONObject input=request.optJSONObject("extras");
            if(input!=null)for(Iterator<String> keys=input.keys();keys.hasNext();){
                String key=keys.next();Object value=input.get(key);
                if(value==JSONObject.NULL)extras.putString(key,null);
                else if(value instanceof Boolean)extras.putBoolean(key,(Boolean)value);
                else if(value instanceof Integer)extras.putInt(key,(Integer)value);
                else if(value instanceof Long)extras.putLong(key,(Long)value);
                else if(value instanceof Number)extras.putDouble(key,((Number)value).doubleValue());
                else extras.putString(key,(String)value);
            }
            String arg=request.isNull("arg")?null:request.optString("arg",null);
            Bundle result=context.getContentResolver().call(uri,request.getString("method"),arg,extras);
            JSONObject output=new JSONObject();if(result!=null)for(String key:result.keySet())output.put(key,JSONObject.wrap(result.get(key)));
            return response.put("result",output);
        }
        throw new IllegalArgumentException("Unknown provider operation");
    }
}
