package local.tv.debugentry;

import java.io.*;
import java.net.*;
import java.nio.*;
import java.nio.charset.StandardCharsets;

/** Speaks only the ADB connection handshake on loopback. */
public final class AdbProbe {
    private static final int CNXN=0x4e584e43, AUTH=0x48545541, STLS=0x534c5453;
    public static final class Result {
        public final int port;public final String state,detail;
        Result(int port,String state,String detail){this.port=port;this.state=state;this.detail=detail;}
    }
    private static void send(OutputStream out,int command,int arg0,int arg1,byte[] data)throws IOException{
        int sum=0;for(byte b:data)sum+=b&255;
        ByteBuffer header=ByteBuffer.allocate(24).order(ByteOrder.LITTLE_ENDIAN);
        header.putInt(command).putInt(arg0).putInt(arg1).putInt(data.length).putInt(sum).putInt(command^-1);
        out.write(header.array());out.write(data);out.flush();
    }
    private static byte[] bytes(InputStream in,int length)throws IOException{
        byte[] data=new byte[length];int at=0;
        while(at<length){int n=in.read(data,at,length-at);if(n<0)throw new EOFException("ADB peer disconnected");at+=n;}
        return data;
    }
    private static int[] packet(InputStream in)throws IOException{
        ByteBuffer header=ByteBuffer.wrap(bytes(in,24)).order(ByteOrder.LITTLE_ENDIAN);
        int command=header.getInt(),arg0=header.getInt();header.getInt();int size=header.getInt();header.getInt();int magic=header.getInt();
        if(magic!=(command^-1)||size<0||size>4096)throw new IOException("Not an ADB handshake");
        bytes(in,size);return new int[]{command,arg0};
    }
    public static Result connect(int port){
        if(port<1||port>65535)throw new IllegalArgumentException("Invalid port");
        try(Socket socket=new Socket()){
            socket.connect(new InetSocketAddress("127.0.0.1",port),500);socket.setSoTimeout(1500);
            send(socket.getOutputStream(),CNXN,0x01000001,4096,"host::features=shell_v2\0".getBytes(StandardCharsets.UTF_8));
            int[] reply=packet(socket.getInputStream());
            if(reply[0]==CNXN)return new Result(port,"connected","ADB connection accepted");
            if(reply[0]==STLS)return new Result(port,"tls_required","This is a TLS ADB endpoint; pairing is still required");
            if(reply[0]!=AUTH||reply[1]!=1)return new Result(port,"unexpected_reply","Not a legacy ADB authentication challenge");
            return new Result(port,"auth_required","Legacy ADB is reachable on the TV itself");
        }catch(ConnectException e){return new Result(port,"closed","No loopback listener");}
        catch(SocketTimeoutException e){return new Result(port,"timeout","No ADB handshake response");}
        catch(IOException e){return new Result(port,"error",e.getClass().getSimpleName()+": "+e.getMessage());}
    }
}
