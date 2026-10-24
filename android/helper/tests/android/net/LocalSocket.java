package android.net;
import java.io.*;
public class LocalSocket implements Closeable {
 boolean created;
 public void connect(LocalSocketAddress address)throws IOException {created=true;}
 public void setSoTimeout(int value)throws IOException {if(!created)throw new IOException("socket not created");}
 public OutputStream getOutputStream(){return new ByteArrayOutputStream();}
 public void close(){}
}
