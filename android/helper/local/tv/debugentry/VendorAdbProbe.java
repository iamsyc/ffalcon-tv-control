package local.tv.debugentry;

import android.content.Context;
import android.net.LocalSocket;
import android.net.LocalSocketAddress;
import org.json.JSONObject;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

public final class VendorAdbProbe {
    private static final String SOCKET="/dev/socket/dft_uds";
    private final Context context;
    private File output;
    private String lastOperation;
    private boolean identityConfirmed;
    VendorAdbProbe(Context context){this.context=context;}
    private LocalSocket connect()throws IOException{
        LocalSocket socket=new LocalSocket();
        try{socket.connect(new LocalSocketAddress(SOCKET,LocalSocketAddress.Namespace.FILESYSTEM));socket.setSoTimeout(1500);return socket;}
        catch(IOException e){socket.close();throw e;}
    }
    public JSONObject inspect()throws Exception{
        JSONObject j=new JSONObject().put("socket",SOCKET).put("socket_exists",new File(SOCKET).exists());
        try{android.system.StructStat stat=android.system.Os.stat(SOCKET);j.put("socket_uid",stat.st_uid).put("socket_gid",stat.st_gid).put("socket_mode",Integer.toOctalString(stat.st_mode));}
        catch(android.system.ErrnoException e){j.put("socket_stat",e.toString());}
        try(LocalSocket socket=connect()){j.put("socket_connect","connected");}
        catch(IOException e){j.put("socket_connect",e.toString());}
        try(Socket socket=new Socket()){socket.connect(new InetSocketAddress("127.0.0.1",27856),600);j.put("factory_tcp_27856","connected");}
        catch(IOException e){j.put("factory_tcp_27856",e.toString());}
        return j;
    }
    public synchronized JSONObject result()throws Exception{
        String text=output!=null&&output.isFile()?new String(Files.readAllBytes(output.toPath()),StandardCharsets.UTF_8):"";
        if("identity".equals(lastOperation))identityConfirmed=text.matches("(?s).*\\buid=(0|1000|2000)\\b.*")&&text.contains("Result: Parcel(00000000")&&!text.contains("Permission Denial");
        return new JSONObject().put("output",text).put("identity_confirmed",identityConfirmed);
    }
    public synchronized JSONObject execute(String operation,String name,String code)throws Exception{
        if(!operation.equals("identity")&&!identityConfirmed)throw new IllegalStateException("First verify the vendor diagnostic service identity");
        File directory=context.getExternalFilesDir(null);
        if(directory==null)throw new IOException("Application external files directory unavailable");
        File next=File.createTempFile("vendor-adb-",".txt",directory);
        String request=VendorAdbCommands.request(operation,next,name,code);
        try(LocalSocket socket=connect()){
            socket.getOutputStream().write(request.getBytes(StandardCharsets.UTF_8));
            socket.getOutputStream().flush();
        }catch(IOException e){next.delete();throw e;}
        if(output!=null)output.delete();output=next;lastOperation=operation;
        Thread.sleep(1000);
        return result().put("operation",operation).put("submitted",true).put("note","A submitted request is not proof of execution; check output and native ADB state");
    }
}
