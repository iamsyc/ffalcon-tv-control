import local.tv.debugentry.AdbProbe;
import local.tv.debugentry.AdbBridge;
import java.io.*;
import java.net.*;
import java.nio.*;
import java.util.*;
import java.util.concurrent.*;

public class AdbChecks {
    static void check(boolean ok,String name){if(!ok)throw new AssertionError(name);System.out.println("PASS "+name);}
    static void reply(Socket socket,int command,int arg0)throws Exception{
        DataInputStream input=new DataInputStream(socket.getInputStream());byte[] request=new byte[24];input.readFully(request);
        ByteBuffer header=ByteBuffer.wrap(request).order(ByteOrder.LITTLE_ENDIAN);
        check(header.getInt()==0x4e584e43,"probe starts with ADB CNXN");header.position(12);input.readFully(new byte[header.getInt()]);
        ByteBuffer response=ByteBuffer.allocate(24).order(ByteOrder.LITTLE_ENDIAN);response.putInt(command).putInt(arg0).putInt(0).putInt(0).putInt(0).putInt(command^-1);
        socket.getOutputStream().write(response.array());
    }
    public static void main(String[] args)throws Exception{
        ExecutorService worker=Executors.newSingleThreadExecutor();
        try{
            for(int command:new int[]{0x48545541,0x4e584e43,0x534c5453})try(ServerSocket server=new ServerSocket(0)){
                Future<?> peer=worker.submit(()->{try(Socket socket=server.accept()){reply(socket,command,1);}catch(Exception e){throw new RuntimeException(e);}});
                String expected=command==0x48545541?"auth_required":command==0x4e584e43?"connected":"tls_required";
                check(AdbProbe.connect(server.getLocalPort()).state.equals(expected),"detects "+expected);peer.get(2,TimeUnit.SECONDS);
            }
            try(ServerSocket backend=new ServerSocket(0);AdbBridge bridge=new AdbBridge(backend.getLocalPort())){
                byte[] sent=new byte[65537];new Random(31).nextBytes(sent);byte[] returned=sent.clone();for(int i=0;i<returned.length;i++)returned[i]^=0x5a;
                Future<?> peer=worker.submit(()->{try(Socket socket=backend.accept()){byte[] received=new byte[sent.length];new DataInputStream(socket.getInputStream()).readFully(received);check(Arrays.equals(sent,received),"bridge forwards exact client bytes");socket.getOutputStream().write(returned);socket.getInputStream().read();}catch(Exception e){throw new RuntimeException(e);}});
                bridge.start();
                try(Socket client=new Socket("127.0.0.1",AdbBridge.PORT)){
                    client.setSoTimeout(3000);client.getOutputStream().write(sent);byte[] received=new byte[returned.length];new DataInputStream(client.getInputStream()).readFully(received);
                    check(Arrays.equals(returned,received),"bridge forwards exact device bytes");bridge.close();check(client.getInputStream().read()==-1,"stop closes active ADB transport");peer.get(2,TimeUnit.SECONDS);
                }
            }
        }finally{worker.shutdownNow();}
        System.out.println("ADB CHECKS PASSED");
    }
}
