package local.tv.debugentry;

import java.io.*;
import java.net.*;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

/** One ordinary ADB transport, forwarded to the TV's own loopback listener. */
public final class AdbBridge implements Closeable {
    public static final int PORT=8766;
    public final int targetPort;
    private final ServerSocket listener;
    private final Set<Socket> clients=ConcurrentHashMap.newKeySet();
    public AdbBridge(int targetPort)throws IOException{this.targetPort=targetPort;listener=new ServerSocket(PORT,1);}
    public void start(){new Thread(()->{
        while(!listener.isClosed())try(Socket remote=listener.accept();Socket local=new Socket()){
            clients.add(remote);clients.add(local);
            try{
                if(listener.isClosed())break;
                local.connect(new InetSocketAddress("127.0.0.1",targetPort),1000);
                new Thread(()->pump(remote,local),"adb-to-tv").start();
                pump(local,remote);
            }finally{clients.remove(remote);clients.remove(local);}
        }catch(IOException ignored){}
    },"adb-loopback-bridge").start();}
    private static void pump(Socket from,Socket to){
        try{InputStream in=from.getInputStream();OutputStream out=to.getOutputStream();byte[] buffer=new byte[16384];int n;while((n=in.read(buffer))!=-1)out.write(buffer,0,n);}
        catch(IOException ignored){}
        finally{closeSocket(from);closeSocket(to);}
    }
    private static void closeSocket(Socket socket){try{socket.close();}catch(IOException ignored){}}
    @Override public void close(){try{listener.close();}catch(IOException ignored){}for(Socket socket:clients)closeSocket(socket);}
}
