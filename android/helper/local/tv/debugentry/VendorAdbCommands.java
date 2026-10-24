package local.tv.debugentry;

import java.io.File;

/** Protocol copied from the installed TCL Logkit Command.toString implementation. */
public final class VendorAdbCommands {
    private static String quote(String s){return "'"+s.replace("'","'\\''")+"'";}
    public static String request(String operation,File output,String serviceName,String password){
        String command;
        switch(operation){
            case "identity": command="/system/bin/id; /system/bin/service call adb 13";break;
            case "pair":
                if(!serviceName.matches("[A-Za-z0-9_-]{1,64}")||!password.matches("[0-9]{6,32}"))throw new IllegalArgumentException("Invalid pairing service name or code");
                // Transaction 9 is enablePairingByQrCode(String serviceName,String password)
                // in the framework.jar pulled from this television.
                command="/system/bin/service call adb 9 s16 "+quote(serviceName)+" s16 "+quote(password);break;
            case "stop-pairing": command="/system/bin/service call adb 11";break;
            default:throw new IllegalArgumentException("Unknown vendor ADB operation");
        }
        String path=output.getAbsolutePath();
        if(path.indexOf(':')>=0||path.indexOf('\n')>=0||path.indexOf('\r')>=0)throw new IllegalArgumentException("Output path cannot contain protocol delimiters");
        return "TV_ADB_PROBE:{ "+command+"; } > "+quote(path)+" 2>&1; /system/bin/chmod 644 "+quote(path)+":\n";
    }
}
