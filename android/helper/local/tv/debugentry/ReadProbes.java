package local.tv.debugentry;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.TimeUnit;

/** Each probe has a fixed command and runs with this application's own UID. */
public final class ReadProbes {
    public static final Map<String,List<String>> COMMANDS;
    static {
        Map<String,List<String>> m=new LinkedHashMap<>();
        m.put("identity",Arrays.asList("/system/bin/id"));
        m.put("properties",Arrays.asList("/system/bin/getprop"));
        m.put("binder-services",Arrays.asList("/system/bin/service","list"));
        m.put("cmd-services",Arrays.asList("/system/bin/cmd","-l"));
        m.put("adb-service",Arrays.asList("/system/bin/dumpsys","adb"));
        m.put("usb-service",Arrays.asList("/system/bin/dumpsys","usb"));
        m.put("usb-device-controllers",Arrays.asList("/system/bin/ls","-l","/sys/class/udc"));
        m.put("usb-gadget-state",Arrays.asList("/system/bin/cat","/sys/class/android_usb/android0/state"));
        m.put("debug-executables",Arrays.asList("/system/bin/ls","-l","/system/bin/adbd","/apex/com.android.adbd/bin/adbd","/system/bin/tclsu"));
        m.put("selinux-state",Arrays.asList("/system/bin/getenforce"));
        m.put("device-policy",Arrays.asList("/system/bin/dumpsys","device_policy"));
        m.put("own-log",Arrays.asList("/system/bin/logcat","-d","-t","120","TvDiagnostic:D","AndroidRuntime:E","*:S"));
        COMMANDS=Collections.unmodifiableMap(m);
    }
    public static final class Result {
        public final String output;public final int exit;public final boolean timeout,truncated;public final long millis;
        Result(String output,int exit,boolean timeout,boolean truncated,long millis){this.output=output;this.exit=exit;this.timeout=timeout;this.truncated=truncated;this.millis=millis;}
    }
    public static Result execute(List<String> command,long timeoutMs)throws Exception{
        if(Thread.currentThread().isInterrupted())throw new InterruptedException("Probe stopped");
        long start=System.nanoTime();Process process=new ProcessBuilder(command).redirectErrorStream(true).start();
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();final boolean[] truncated={false};
        Thread reader=new Thread(()->{try(InputStream in=process.getInputStream()){
            byte[] buffer=new byte[4096];int n;while((n=in.read(buffer))!=-1){int remaining=1024*1024-bytes.size();if(remaining>0)bytes.write(buffer,0,Math.min(n,remaining));if(n>remaining)truncated[0]=true;}
        }catch(IOException ignored){}},"tv-probe-output");reader.start();
        try {
            boolean finished=process.waitFor(timeoutMs,TimeUnit.MILLISECONDS);
            if(!finished){process.destroyForcibly();process.waitFor(1000,TimeUnit.MILLISECONDS);}
            reader.join(1000);
            if(reader.isAlive()){process.getInputStream().close();reader.join(1000);}
            return new Result(new String(bytes.toByteArray(),StandardCharsets.UTF_8),finished?process.exitValue():-1,!finished,truncated[0],TimeUnit.NANOSECONDS.toMillis(System.nanoTime()-start));
        }finally{
            if(process.isAlive())process.destroyForcibly();
            if(reader.isAlive())process.getInputStream().close();
        }
    }
}
