import local.tv.debugentry.LocalServer;
import local.tv.debugentry.ReadProbes;
import java.net.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.*;

public class CoreChecks {
    static int passed;
    static final String TOKEN="0123456789abcdef0123456789abcdef";
    static void check(boolean condition,String message){if(!condition)throw new AssertionError(message);passed++;System.out.println("PASS "+message);}
    static byte[] request(int port,String request,byte[] body)throws Exception{
        try(Socket socket=new Socket("127.0.0.1",port)){socket.setSoTimeout(2500);socket.getOutputStream().write(request.getBytes(StandardCharsets.US_ASCII));if(body!=null)socket.getOutputStream().write(body);socket.getOutputStream().flush();return socket.getInputStream().readAllBytes();}
    }
    static String text(byte[] bytes){return new String(bytes,StandardCharsets.UTF_8);}
    static byte[] content(byte[] response){for(int i=0;i+3<response.length;i++)if(response[i]==13&&response[i+1]==10&&response[i+2]==13&&response[i+3]==10)return Arrays.copyOfRange(response,i+4,response.length);throw new AssertionError("No HTTP header terminator");}
    static void stalledDownloadsRecover()throws Exception{
        File file=File.createTempFile("tv-stalled-download",".apk");
        try(RandomAccessFile output=new RandomAccessFile(file,"rw")){output.setLength(32*1024*1024);}
        LocalServer server=new LocalServer(0,TOKEN,r->r.route.equals("file")?LocalServer.Response.file(file,"application/octet-stream"):LocalServer.Response.json(200,"{}"));
        List<Socket> stalled=new ArrayList<>();server.start();
        try{
            for(int i=0;i<2;i++){
                Socket socket=new Socket("127.0.0.1",server.port());stalled.add(socket);socket.setReceiveBufferSize(1024);socket.setSoTimeout(2500);
                socket.getOutputStream().write(("GET /"+TOKEN+"/file HTTP/1.1\r\n\r\n").getBytes(StandardCharsets.US_ASCII));
                if(socket.getInputStream().read()!='H')throw new AssertionError("Download did not start");
            }
            System.out.println("Checking automatic recovery from two stalled downloads (up to 65 seconds)...");
            try(Socket status=new Socket("127.0.0.1",server.port())){
                status.setSoTimeout(65000);status.getOutputStream().write(("GET /"+TOKEN+"/status HTTP/1.1\r\n\r\n").getBytes(StandardCharsets.US_ASCII));
                check(text(status.getInputStream().readAllBytes()).startsWith("HTTP/1.1 200"),"stalled downloads release workers and status recovers");
            }
        }finally{server.close();for(Socket socket:stalled)socket.close();file.delete();}
    }
    public static void main(String[] args)throws Exception{
        AtomicInteger calls=new AtomicInteger();AtomicReference<LocalServer.Request> last=new AtomicReference<>();File file=File.createTempFile("tv-core-file",".bin");byte[] original=new byte[65537];new Random(73).nextBytes(original);Files.write(file.toPath(),original);
        LocalServer server=new LocalServer(0,TOKEN,r->{calls.incrementAndGet();last.set(r);if(r.route.equals("file"))return LocalServer.Response.file(file,"application/octet-stream");if(r.route.equals("echo"))return LocalServer.Response.bytes("application/octet-stream",r.body);return LocalServer.Response.json(200,"{\"ok\":true}");});server.start();int port=server.port();String path="/"+TOKEN+"/";
        try{
            check(text(request(port,"GET /report HTTP/1.1\r\nHost: localhost\r\n\r\n",null)).startsWith("HTTP/1.1 403"),"missing token rejected");
            check(calls.get()==0,"unauthorized request never reaches handler");
            byte[] response=request(port,"GET "+path+"report?package=com.tcl.settings&label=%E8%B0%83%E8%AF%95 HTTP/1.1\r\nHost: localhost\r\n\r\n",null);
            check(text(response).startsWith("HTTP/1.1 200"),"authenticated GET succeeds");
            check(last.get().route.equals("report")&&last.get().query.get("label").equals("调试"),"route and UTF-8 parameters delivered correctly");
            int before=calls.get();check(text(request(port,"DELETE "+path+"report HTTP/1.1\r\n\r\n",null)).startsWith("HTTP/1.1 405")&&calls.get()==before,"unsupported method blocked before handler");
            byte[] payload=new byte[1024*1024+17];new Random(17).nextBytes(payload);response=request(port,"POST "+path+"echo HTTP/1.1\r\nContent-Length: "+payload.length+"\r\n\r\n",payload);check(Arrays.equals(payload,content(response)),"binary POST survives complete transfer");
            check(Arrays.equals(original,content(request(port,"GET "+path+"file HTTP/1.1\r\n\r\n",null))),"APK-style file response is byte-exact");
            before=calls.get();check(text(request(port,"POST "+path+"echo HTTP/1.1\r\nContent-Length: "+(LocalServer.MAX_BODY+1)+"\r\n\r\n",null)).startsWith("HTTP/1.1 413")&&calls.get()==before,"oversized upload rejected before allocation or handler");
            check(text(request(port,"POST "+path+"echo HTTP/1.1\r\nTransfer-Encoding: chunked\r\n\r\n",null)).startsWith("HTTP/1.1 413"),"unsupported chunked upload rejected");
            before=calls.get();try(Socket socket=new Socket("127.0.0.1",port)){socket.setSoTimeout(2000);socket.getOutputStream().write(("POST "+path+"echo HTTP/1.1\r\nContent-Length: 100\r\n\r\nshort").getBytes(StandardCharsets.US_ASCII));socket.shutdownOutput();socket.getInputStream().readAllBytes();}check(calls.get()==before,"incomplete upload never reaches update handler");
            check(text(request(port,"GET "+path+"status HTTP/1.1\r\n\r\n",null)).startsWith("HTTP/1.1 200"),"server remains usable after interrupted upload");
            try(Socket idle=new Socket("127.0.0.1",port)){idle.setSoTimeout(1500);Thread.sleep(60);server.close();check(idle.getInputStream().read()==-1,"stop closes an active client immediately");}
        }finally{server.close();file.delete();}
        ReadProbes.Result small=ReadProbes.execute(Arrays.asList("/usr/bin/printf","probe-output"),1000);check(small.exit==0&&!small.timeout&&small.output.equals("probe-output"),"probe output and exit status captured");
        ReadProbes.Result timeout=ReadProbes.execute(Arrays.asList("/bin/sleep","4"),100);check(timeout.timeout&&timeout.exit==-1&&timeout.millis<2000,"probe timeout terminates the child process");
        ReadProbes.Result large=ReadProbes.execute(Arrays.asList("/usr/bin/python3","-c","import sys;sys.stdout.write('x'*1200000)"),5000);check(large.exit==0&&large.truncated&&large.output.length()==1048576,"large output drains without deadlock and is bounded");
        AtomicBoolean cancelled=new AtomicBoolean();Thread probe=new Thread(()->{try{ReadProbes.execute(Arrays.asList("/bin/sleep","10"),15000);}catch(InterruptedException e){cancelled.set(true);}catch(Exception e){throw new RuntimeException(e);}});probe.start();Thread.sleep(100);probe.interrupt();probe.join(1500);check(!probe.isAlive()&&cancelled.get(),"stopping a running probe cancels its wait and cleans up the child");
        check(!ReadProbes.COMMANDS.containsKey("shell")&&!ReadProbes.COMMANDS.containsKey("root"),"remote probe registry contains no arbitrary shell or root entry");
        stalledDownloadsRecover();
        System.out.println("CHECKS PASSED: "+passed);
    }
}
