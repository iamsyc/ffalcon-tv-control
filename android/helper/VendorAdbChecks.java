import local.tv.debugentry.VendorAdbCommands;
import java.nio.file.*;
import java.io.*;

public class VendorAdbChecks {
    static int count;
    static void check(boolean value,String message){if(!value)throw new AssertionError(message);count++;}
    public static void main(String[] args)throws Exception{
        Path dir=Files.createTempDirectory("vendor-adb-check-");
        File file=dir.resolve("TV's output.txt").toFile();
        String request=VendorAdbCommands.request("pair",file,"tv_adb_probe","123456");
        String[] fields=request.strip().split(":",-1);
        check(fields.length==3&&fields[0].equals("TV_ADB_PROBE")&&fields[2].isEmpty(),"TCL three-field wire protocol");
        Path bin=Files.createDirectory(dir.resolve("bin"));
        Files.writeString(bin.resolve("service"),"#!/bin/sh\nprintf '%s\\n' \"$@\"\n");
        bin.resolve("service").toFile().setExecutable(true);
        Files.createSymbolicLink(bin.resolve("chmod"),Path.of("/bin/chmod"));
        String script=fields[1].replace("/system/bin/",bin+"/");
        check(new ProcessBuilder("/bin/sh","-c",script).inheritIO().start().waitFor()==0,"Generated shell command runs with quoted output path");
        check(Files.readString(file.toPath()).equals("call\nadb\n9\ns16\ntv_adb_probe\ns16\n123456\n"),"Exact framework transaction and argument order");
        try{VendorAdbCommands.request("pair",file,"bad;id","123456");throw new AssertionError("Accepted shell syntax");}catch(IllegalArgumentException expected){count++;}
        try{VendorAdbCommands.request("pair",file,"tv_probe","123456\nreboot");throw new AssertionError("Accepted protocol newline");}catch(IllegalArgumentException expected){count++;}
        check(VendorAdbCommands.request("stop-pairing",file,"","").contains("service call adb 11"),"Pairing shutdown transaction");
        check(VendorAdbCommands.request("identity",file,"","").contains("/system/bin/id; /system/bin/service call adb 13"),"Identity and read-only capability probe");
        System.out.println(count+" vendor ADB checks passed");
    }
}
