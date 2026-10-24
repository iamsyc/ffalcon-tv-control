import java.lang.reflect.*;
public class SocketLifecycleCheck {
 public static void main(String[] args)throws Exception {
  Class<?> c=Class.forName("local.tv.debugentry.VendorAdbProbe");
  Constructor<?> ctor=c.getDeclaredConstructors()[0];ctor.setAccessible(true);
  Object instance=ctor.newInstance((Object)null);
  Method connect=c.getDeclaredMethod("connect");connect.setAccessible(true);
  connect.invoke(instance);
  System.out.println("LocalSocket lifecycle passed");
 }
}
