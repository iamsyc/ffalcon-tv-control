import local.tv.debugentry.ReadProbes;
import java.util.*;
public class CommandChecks {
 public static void main(String[] args)throws Exception {
  String literal="$(id); `id` $HOME";
  ReadProbes.Result text=ReadProbes.execute(Arrays.asList("/usr/bin/printf","%s",literal),1000);
  if(text.exit!=0||!literal.equals(text.output))throw new AssertionError("Argument list was altered or interpreted");
  ReadProbes.Result timed=ReadProbes.execute(Arrays.asList("/bin/sleep","3"),100);
  if(!timed.timeout||timed.millis>2500)throw new AssertionError("Command timeout failed");
  System.out.println("Argument preservation and process timeout checks passed");
 }
}
