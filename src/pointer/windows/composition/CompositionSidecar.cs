// Draws a live Windows Composition backdrop below one fixed Pointer Qt window.
// Qt remains a separate layered top-level window so its text stays sharp. The
// helper never owns or reparents Qt; helper teardown cannot destroy the app.
// JSON lines use physical pixels for geometry and DIP for Gaussian sigma.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Numerics;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using Windows.UI.Composition;
using Windows.UI.Composition.Desktop;

class SidecarNative {
    [DllImport("kernel32.dll",SetLastError=true)] public static extern IntPtr GetStdHandle(int kind);
    [DllImport("kernel32.dll",SetLastError=true)] public static extern uint GetFileType(IntPtr handle);
    [DllImport("kernel32.dll",SetLastError=true)] public static extern bool ReadFile(IntPtr handle,byte[] buffer,uint size,out uint read,IntPtr overlapped);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hwnd,out uint pid);
    [DllImport("user32.dll")] public static extern bool IsWindow(IntPtr hwnd);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hwnd);
    [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hwnd);
    [DllImport("user32.dll")] public static extern IntPtr GetWindow(IntPtr hwnd,uint command);
    [DllImport("user32.dll",CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr hwnd,StringBuilder text,int maximum);
    [DllImport("user32.dll",CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr hwnd,StringBuilder text,int maximum);
    [DllImport("user32.dll",SetLastError=true)] public static extern bool SetWindowPos(IntPtr hwnd,IntPtr after,int x,int y,int width,int height,uint flags);
    [DllImport("user32.dll",SetLastError=true)] public static extern bool SetProcessDpiAwarenessContext(IntPtr context);
}

class SidecarForm : Form {
    public SidecarForm() { Text="Pointer official Composition backdrop sidecar"; FormBorderStyle=FormBorderStyle.None; ShowInTaskbar=false; StartPosition=FormStartPosition.Manual; Bounds=new Rectangle(0,0,1,1); }
    protected override CreateParams CreateParams { get { var cp=base.CreateParams; cp.ExStyle|=0x00200000|0x08000000|0x00000080; return cp; } }
    protected override bool ShowWithoutActivation { get { return true; } }
    protected override void OnPaintBackground(PaintEventArgs e) {}
    protected override void OnPaint(PaintEventArgs e) {}
    protected override void WndProc(ref Message message) {
        if(message.Msg==0x21) { message.Result=new IntPtr(3); return; }
        base.WndProc(ref message);
    }
}

class SidecarScene : IDisposable {
    public readonly SidecarForm Window=new SidecarForm();
    private Compositor compositor;
    private DesktopWindowTarget target;
    private CompositionEffectBrush brush;
    private SpriteVisual sprite;
    private CompositionRoundedRectangleGeometry geometry;
    private IntPtr queue;
    private IntPtr hwnd;
    private bool requestedVisible;
    public SidecarScene() {
        hwnd=Window.Handle;
        Native.QueueOptions options=new Native.QueueOptions(); options.Size=12; options.ThreadType=2; options.ApartmentType=2;
        Marshal.ThrowExceptionForHR(Native.CreateDispatcherQueueController(options,out queue)); compositor=new Compositor();
        int enabled=1; Marshal.ThrowExceptionForHR(Native.DwmSetWindowAttribute(hwnd,17,ref enabled,4));
        // This HWND contains only the backdrop. Attaching Composition to Qt's
        // HWND would place the effect above Qt's raster backing store.
        IntPtr raw; ((ICompositorDesktopInterop)(object)compositor).CreateDesktopWindowTarget(hwnd,false,out raw); target=(DesktopWindowTarget)Marshal.GetObjectForIUnknown(raw); Marshal.Release(raw);
        sprite=compositor.CreateSpriteVisual(); sprite.Opacity=1; target.Root=sprite;
        GaussianDescription effect=new GaussianDescription(); effect.Name="Blur"; effect.Sigma=24; effect.Source=new CompositionEffectSourceParameter("Backdrop");
        var factory=compositor.CreateEffectFactory(effect,new string[]{"Blur.StandardDeviation"}); brush=factory.CreateBrush(); brush.SetSourceParameter("Backdrop",compositor.CreateHostBackdropBrush()); sprite.Brush=brush;
        geometry=compositor.CreateRoundedRectangleGeometry(); sprite.Clip=compositor.CreateGeometricClip(geometry);
    }
    public void Apply(IntPtr qt,bool visible,int x,int y,int width,int height,int radius,float sigma) {
        requestedVisible=visible;
        brush.Properties.InsertScalar("Blur.StandardDeviation",sigma); sprite.Size=new Vector2(width,height);
        float r=Math.Min(radius,Math.Min(width,height)/2.0f);
        // Sidebar's right edge joins opaque Qt content. Place the right rounded
        // corners outside the sprite while preserving the two outer left ones.
        geometry.Size=new Vector2(width+2*r,height); geometry.CornerRadius=new Vector2(r,r);
        if(visible) {
            // Insert only our HWND immediately below Qt. An owner relationship
            // would cause Windows to destroy Qt when this helper exits.
            Marshal.ThrowExceptionForHR(SidecarNative.SetWindowPos(hwnd,qt,x,y,width,height,0x10|0x40)?0:Marshal.GetHRForLastWin32Error());
        } else Hide();
    }
    public void MaintainPlacement(IntPtr qt) {
        if(!requestedVisible||hwnd==IntPtr.Zero||!SidecarNative.IsWindowVisible(hwnd)||
           !SidecarNative.IsWindowVisible(qt)||SidecarNative.IsIconic(qt)) return;
        // Another window can enter between Qt and our backdrop without moving
        // Qt or changing the desired state. Repair only our position in that
        // order, preserving geometry, visibility, activation, and ownership.
        // WinForms' hidden IME window can sit above its own visible Form. Skip
        // invisible entries to avoid repairing an already correct visual order.
        IntPtr next=SidecarNative.GetWindow(qt,2);
        for(int count=0;count<64&&next!=IntPtr.Zero&&next!=hwnd&&!SidecarNative.IsWindowVisible(next);count++)
            next=SidecarNative.GetWindow(next,2);
        if(next!=hwnd)
            Marshal.ThrowExceptionForHR(SidecarNative.SetWindowPos(hwnd,qt,0,0,0,0,0x10|0x1|0x2)?0:Marshal.GetHRForLastWin32Error());
    }
    public void Hide() { if(hwnd!=IntPtr.Zero) Native.ShowWindow(hwnd,0); }
    public void Dispose() {
        Hide();
        if(target!=null) { target.Root=null; target.Dispose(); target=null; }
        if(brush!=null) { brush.Dispose(); brush=null; }
        if(sprite!=null) { sprite.Dispose(); sprite=null; }
        if(geometry!=null) { geometry.Dispose(); geometry=null; }
        if(compositor!=null) { compositor.Dispose(); compositor=null; }
        if(queue!=IntPtr.Zero) { Marshal.Release(queue); queue=IntPtr.Zero; }
        Window.Dispose(); hwnd=IntPtr.Zero;
    }
}

class SidecarProgram {
    private static JavaScriptSerializer serializer=new JavaScriptSerializer();
    private static SidecarScene scene;
    private static Process parent;
    private static IntPtr qt;
    private static uint targetPid;
    private static bool exiting;
    private static void Emit(object message) { Console.Out.WriteLine(serializer.Serialize(message)); Console.Out.Flush(); }
    private static bool ValidateTarget() {
        uint actual; if(parent.HasExited||!SidecarNative.IsWindow(qt)) return false;
        SidecarNative.GetWindowThreadProcessId(qt,out actual); return actual==targetPid;
    }
    private static void Exit() { if(exiting) return; exiting=true; if(scene!=null) scene.Hide(); Application.ExitThread(); }
    private static void Fail(string code,string message,long? seq) { var error=new Dictionary<string,object>{{"event","error"},{"code",code},{"message",message}}; if(seq.HasValue) error["seq"]=seq.Value; Emit(error); Console.Error.WriteLine(code+": "+message); Exit(); }
    private static long Integer(Dictionary<string,object> command,string name,long min,long max) {
        object raw; if(!command.TryGetValue(name,out raw)||raw is bool||!(raw is int||raw is long||raw is decimal||raw is double)) throw new FormatException(name+" must be an integer");
        decimal value=Convert.ToDecimal(raw); if(value!=decimal.Truncate(value)||value<min||value>max) throw new FormatException(name+" is outside the valid integer range"); return (long)value;
    }
    private static IEnumerable<string> ReadInputLines() {
        IntPtr input=SidecarNative.GetStdHandle(-10);
        if(input==IntPtr.Zero||input==new IntPtr(-1)) throw new IOException("The redirected standard input handle is invalid.");
        bool pipe=SidecarNative.GetFileType(input)==3;
        byte[] chunk=new byte[4096], line=new byte[8193]; int length=0;
        var utf8=new UTF8Encoding(false,true);
        while(true) {
            uint received; bool ok=SidecarNative.ReadFile(input,chunk,(uint)chunk.Length,out received,IntPtr.Zero);
            int error=Marshal.GetLastWin32Error();
            if(!ok&&error!=109&&error!=232) throw new System.ComponentModel.Win32Exception(error);
            // A successful zero-byte pipe read can come from an empty peer
            // write. Only a closing/broken pipe means EOF on this transport.
            if(ok&&received==0&&pipe) continue;
            if(!ok||received==0) {
                if(length>0) yield return utf8.GetString(line,0,line[length-1]==13?length-1:length);
                yield break;
            }
            for(int index=0;index<received;index++) {
                byte value=chunk[index];
                if(value==10) {
                    yield return utf8.GetString(line,0,length>0&&line[length-1]==13?length-1:length);
                    length=0;
                } else {
                    if(length>=8192&&(length!=8192||value!=13)) throw new FormatException("JSON command exceeds 8192 UTF-8 bytes");
                    line[length++]=value;
                }
            }
        }
    }
    private static void Handle(string line) {
        if(exiting) return; long? seq=null;
        try {
            var command=serializer.Deserialize<Dictionary<string,object>>(line); if(command==null) throw new FormatException("JSON object required");
            object action; if((command.TryGetValue("command",out action)||command.TryGetValue("event",out action))&&Convert.ToString(action)=="quit") { Exit(); return; }
            seq=Integer(command,"seq",0,long.MaxValue); if(!ValidateTarget()) { Fail("target_lost","The fixed Qt HWND no longer belongs to the fixed live target process.",seq); return; }
            object visibility; if(!command.TryGetValue("visible",out visibility)||!(visibility is bool)) throw new FormatException("visible must be a boolean");
            int x=(int)Integer(command,"x",-100000,100000), y=(int)Integer(command,"y",-100000,100000);
            int width=(int)Integer(command,"width",1,32768), height=(int)Integer(command,"height",1,32768), radius=(int)Integer(command,"radius",0,32768);
            object rawSigma; if(!command.TryGetValue("sigma",out rawSigma)||!(rawSigma is int||rawSigma is long||rawSigma is decimal||rawSigma is double)) throw new FormatException("sigma must be numeric");
            float sigma=Convert.ToSingle(rawSigma); if(float.IsNaN(sigma)||float.IsInfinity(sigma)||sigma<0||sigma>48) throw new FormatException("sigma must be between 0 and 48 DIP");
            bool visible=(bool)visibility&&SidecarNative.IsWindowVisible(qt)&&!SidecarNative.IsIconic(qt);
            scene.Apply(qt,visible,x,y,width,height,radius,sigma); Emit(new Dictionary<string,object>{{"event","applied"},{"seq",seq.Value}});
        } catch(Exception ex) { Fail("update_failed",ex.Message,seq); Console.Error.WriteLine(ex); }
    }
    [STAThread] static int Main(string[] arguments) {
        // A GUI executable has no console. Encoding setters call console APIs
        // and fail even when QProcess redirects valid standard stream handles.
        var utf8=new UTF8Encoding(false);
        Console.SetOut(new StreamWriter(Console.OpenStandardOutput(),utf8){AutoFlush=true});
        Console.SetError(new StreamWriter(Console.OpenStandardError(),utf8){AutoFlush=true});
        serializer.MaxJsonLength=8192;
        try {
            if(arguments.Length!=4||arguments[0]!="--pid"||arguments[2]!="--hwnd") throw new ArgumentException("Usage: CompositionSidecar.exe --pid <decimal PID> --hwnd <decimal HWND>");
            targetPid=uint.Parse(arguments[1]); qt=new IntPtr(long.Parse(arguments[3])); parent=Process.GetProcessById((int)targetPid); IntPtr processHandle=parent.Handle;
            if(!ValidateTarget()) throw new ArgumentException("Target HWND/PID association is invalid.");
            var title=new StringBuilder(256); var className=new StringBuilder(256); SidecarNative.GetWindowText(qt,title,title.Capacity); SidecarNative.GetClassName(qt,className,className.Capacity);
            if(!title.ToString().StartsWith("Pointer",StringComparison.Ordinal)||!className.ToString().StartsWith("Qt",StringComparison.Ordinal)) throw new ArgumentException("Target must be the specified Pointer Qt window.");
            if(!SidecarNative.SetProcessDpiAwarenessContext(new IntPtr(-4))) Marshal.ThrowExceptionForHR(Marshal.GetHRForLastWin32Error());
            Application.EnableVisualStyles(); scene=new SidecarScene();
            Application.ThreadException+=delegate(object sender,ThreadExceptionEventArgs error) { Fail("helper_failed",error.Exception.Message,null); Console.Error.WriteLine(error.Exception); };
            Emit(new Dictionary<string,object>{{"event","ready"},{"protocol",1},{"pid",targetPid},{"hwnd",qt.ToInt64()}});
            var watcher=new System.Windows.Forms.Timer(); watcher.Interval=100; watcher.Tick+=delegate { if(!ValidateTarget()) Exit(); else if(!SidecarNative.IsWindowVisible(qt)||SidecarNative.IsIconic(qt)) scene.Hide(); else scene.MaintainPlacement(qt); }; watcher.Start();
            // Qt's named stdin pipe can retain delayed data while Console.In is
            // blocked. ReadFile on this borrowed handle handles delayed writes
            // correctly; decode after LF framing so split UTF-8 stays intact.
            Thread input=new Thread(delegate() { try { foreach(string line in ReadInputLines()) { string captured=line; scene.Window.BeginInvoke((Action)delegate { Handle(captured); }); } scene.Window.BeginInvoke((Action)Exit); } catch(Exception ex) { try { scene.Window.BeginInvoke((Action)delegate { Fail("input_failed",ex.Message,null); }); } catch { } } }); input.IsBackground=true; input.Start();
            Application.Run(); watcher.Stop(); watcher.Dispose();
            return 0;
        } catch(Exception ex) { Emit(new Dictionary<string,object>{{"event","error"},{"code","startup_failed"},{"message",ex.Message}}); Console.Error.WriteLine(ex); return 1; }
        finally { exiting=true; if(scene!=null) scene.Dispose(); if(parent!=null) parent.Dispose(); }
    }
}
