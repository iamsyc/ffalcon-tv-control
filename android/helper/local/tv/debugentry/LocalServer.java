package local.tv.debugentry;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;

/** Token-protected local diagnostics transport. Commands run with the diagnostic application UID and require its TV control toggle. */
public final class LocalServer implements Closeable {
    public interface Handler { Response handle(Request request) throws Exception; }
    public static final int MAX_BODY = 16 * 1024 * 1024;
    public static final class Request {
        public final String method, route;
        public final Map<String,String> query;
        public final byte[] body;
        Request(String method, String route, Map<String,String> query, byte[] body) {
            this.method=method; this.route=route; this.query=query; this.body=body;
        }
        public String text() { return new String(body, StandardCharsets.UTF_8); }
    }
    public static final class Response {
        final int code; final String type; final byte[] bytes; final File file;
        private Response(int code,String type,byte[] bytes,File file) {
            this.code=code;this.type=type;this.bytes=bytes;this.file=file;
        }
        public static Response json(int code,String value) {
            return new Response(code,"application/json; charset=utf-8",value.getBytes(StandardCharsets.UTF_8),null);
        }
        public static Response bytes(String type,byte[] bytes) {return new Response(200,type,bytes,null);}
        public static Response file(File file,String type) {return new Response(200,type,null,file);}
    }
    private final String prefix;
    private final Handler handler;
    private final ExecutorService workers=Executors.newFixedThreadPool(2);
    private final ScheduledExecutorService timeouts=Executors.newSingleThreadScheduledExecutor();
    private final Set<Socket> clients=ConcurrentHashMap.newKeySet();
    private final ServerSocket listener;
    public LocalServer(int port,String token,Handler handler) throws IOException {
        if(!token.matches("[a-f0-9]{32}")) throw new IllegalArgumentException("Invalid token");
        this.prefix="/"+token+"/";this.handler=handler;
        listener=new ServerSocket(port,4);
    }
    public int port(){return listener.getLocalPort();}
    public void start(){new Thread(()->{
        while(!listener.isClosed())try{
            Socket socket=listener.accept();
            if(!socket.getInetAddress().isSiteLocalAddress()&&!socket.getInetAddress().isLoopbackAddress()) {socket.close();continue;}
            clients.add(socket);
            try {workers.execute(()->serve(socket));}catch(RejectedExecutionException e){clients.remove(socket);socket.close();}
        }catch(IOException e){if(!listener.isClosed())close();}
    },"tv-local-listener").start();}
    private void serve(Socket socket){ScheduledFuture<?> deadline=null;try(Socket owned=socket){
        // A stalled upload or download must release its worker.
        deadline=timeouts.schedule(()->{try{socket.close();}catch(IOException ignored){}},60,TimeUnit.SECONDS);
        owned.setSoTimeout(5000);
        InputStream input=owned.getInputStream();String first=line(input,8192);
        if(first==null)return;
        String[] request=first.split(" ");
        if(request.length!=3){send(owned,Response.json(400,"{\"error\":\"malformed_request\"}"));return;}
        String path=request[1];
        long length=0;int headers=0;boolean chunked=false;
        for(String header;(header=line(input,8192))!=null&&!header.isEmpty();){
            if(++headers>64)throw new IOException("Too many headers");
            int colon=header.indexOf(':');if(colon<1)continue;
            String name=header.substring(0,colon).toLowerCase(Locale.ROOT);
            String value=header.substring(colon+1).trim();
            if(name.equals("content-length"))length=Long.parseLong(value);
            if(name.equals("transfer-encoding"))chunked=true;
        }
        if(!request[0].equals("GET")&&!request[0].equals("POST")){send(owned,Response.json(405,"{\"error\":\"method_not_allowed\"}"));return;}
        if(!path.startsWith(prefix)){send(owned,Response.json(403,"{\"error\":\"token_required\"}"));return;}
        if(chunked||length<0||length>MAX_BODY){send(owned,Response.json(413,"{\"error\":\"use_content_length_max_16MiB\"}"));return;}
        byte[] body=new byte[(int)length];int at=0;
        while(at<body.length){int n=input.read(body,at,body.length-at);if(n<0)throw new EOFException("Incomplete body");at+=n;}
        int q=path.indexOf('?');String route=path.substring(prefix.length(),q<0?path.length():q);
        Map<String,String> params=new LinkedHashMap<>();
        if(q>=0)for(String pair:path.substring(q+1).split("&")){
            String[] bits=pair.split("=",2);
            params.put(URLDecoder.decode(bits[0],"UTF-8"),bits.length==2?URLDecoder.decode(bits[1],"UTF-8"):"");
        }
        try{send(owned,handler.handle(new Request(request[0],route,params,body)));}
        catch(Exception e){send(owned,Response.json(500,"{\"error\":\"request_failed\",\"type\":\""+e.getClass().getSimpleName()+"\"}"));}
    }catch(IOException|IllegalArgumentException|RejectedExecutionException ignored){}finally{if(deadline!=null)deadline.cancel(false);clients.remove(socket);}}
    private static String line(InputStream in,int limit)throws IOException{
        ByteArrayOutputStream value=new ByteArrayOutputStream();int c;
        while((c=in.read())!=-1){if(c=='\n')break;if(c!='\r')value.write(c);if(value.size()>limit)throw new IOException("Line too long");}
        return c==-1&&value.size()==0?null:value.toString("US-ASCII");
    }
    private static void send(Socket socket,Response response)throws IOException{
        long size=response.file==null?response.bytes.length:response.file.length();
        String header="HTTP/1.1 "+response.code+" Result\r\nContent-Type: "+response.type+"\r\nContent-Length: "+size+"\r\nConnection: close\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nContent-Security-Policy: default-src 'none'\r\n\r\n";
        OutputStream out=socket.getOutputStream();out.write(header.getBytes(StandardCharsets.US_ASCII));
        if(response.file==null)out.write(response.bytes);else try(InputStream in=new FileInputStream(response.file)){
            byte[] buffer=new byte[16384];int n;while((n=in.read(buffer))!=-1)out.write(buffer,0,n);
        }
        out.flush();
    }
    @Override public void close(){
        try{listener.close();}catch(IOException ignored){}
        for(Socket client:clients)try{client.close();}catch(IOException ignored){}
        workers.shutdownNow();
        timeouts.shutdownNow();
    }
}
