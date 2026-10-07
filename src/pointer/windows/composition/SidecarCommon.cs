// Public Composition and Direct2D effect interop used by CompositionSidecar.
// The operating system supplies WinRT metadata and .NET Framework supplies the
// projection; no third-party effect package or desktop screenshot is used.
using System;
using System.IO;
using System.Drawing;
using System.Runtime.InteropServices;
using System.Numerics;
using System.Windows.Forms;
using Windows.Graphics.Effects;
using Windows.UI.Composition;
using Windows.UI.Composition.Desktop;

[ComImport, Guid("29E691FA-4567-4DCA-B319-D0F207EB6807"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface ICompositorDesktopInterop {
    void CreateDesktopWindowTarget(IntPtr hwnd, [MarshalAs(UnmanagedType.Bool)] bool topmost, out IntPtr target);
    void EnsureOnThread(uint id);
}

[ComVisible(true), Guid("2FC57384-A068-44D7-A331-30982FCF7177"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IGraphicsEffectD2D1Interop {
    [PreserveSig] int GetEffectId(out Guid id);
    [PreserveSig] int GetNamedPropertyMapping([MarshalAs(UnmanagedType.LPWStr)] string name, out uint index, out uint mapping);
    [PreserveSig] int GetPropertyCount(out uint count);
    [PreserveSig] int GetProperty(uint index, out IntPtr value);
    [PreserveSig] int GetSource(uint index, [MarshalAs(UnmanagedType.Interface)] out IGraphicsEffectSource source);
    [PreserveSig] int GetSourceCount(out uint count);
}

[ComVisible(true), ClassInterface(ClassInterfaceType.None)]
public class GaussianDescription : IGraphicsEffect, IGraphicsEffectD2D1Interop {
    public string Name { get; set; }
    public float Sigma;
    public IGraphicsEffectSource Source;
    public int GetEffectId(out Guid id) { id = new Guid("1FEB6D69-2FE6-4AC9-8C58-1D7F93E7A6A5"); return 0; }
    public int GetNamedPropertyMapping(string name, out uint index, out uint mapping) {
        index = 0; mapping = 1;
        if (name == "StandardDeviation") return 0;
        if (name == "Optimization") { index=1; return 0; }
        if (name == "BorderMode") { index=2; return 0; }
        return unchecked((int)0x80070057);
    }
    public int GetPropertyCount(out uint count) { count=3; return 0; }
    public int GetProperty(uint index, out IntPtr value) {
        value=IntPtr.Zero;
        if (index==0) { value=Native.BoxSingle(Sigma); return 0; }
        if (index==1) { value=Native.BoxUInt32(2); return 0; }
        if (index==2) { value=Native.BoxUInt32(1); return 0; }
        return unchecked((int)0x80070057);
    }
    public int GetSource(uint index, out IGraphicsEffectSource source) { source=index==0 ? Source : null; return index==0 ? 0 : unchecked((int)0x80070057); }
    public int GetSourceCount(out uint count) { count=1; return 0; }
}

class Native {
    [DllImport("combase.dll", CharSet=CharSet.Unicode)] public static extern int WindowsCreateString(string value, int length, out IntPtr hstring);
    [DllImport("combase.dll")] public static extern int WindowsDeleteString(IntPtr hstring);
    [DllImport("combase.dll")] public static extern int RoGetActivationFactory(IntPtr hstring, ref Guid iid, out IntPtr factory);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] private delegate int CreateSingleDelegate(IntPtr self, float value, out IntPtr boxed);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] private delegate int CreateUInt32Delegate(IntPtr self, uint value, out IntPtr boxed);
    private static IntPtr valueFactory;
    private static IntPtr PropertyValueFactory() {
        if(valueFactory!=IntPtr.Zero) return valueFactory;
        string name="Windows.Foundation.PropertyValue"; IntPtr hs; Marshal.ThrowExceptionForHR(WindowsCreateString(name,name.Length,out hs));
        Guid id=new Guid("629BDBC8-D932-4FF4-96B9-8D96C5C1E858"); int hr=RoGetActivationFactory(hs,ref id,out valueFactory); WindowsDeleteString(hs); Marshal.ThrowExceptionForHR(hr); return valueFactory;
    }
    private static IntPtr PropertyValueInterface(IntPtr boxed) {
        // GetProperty's ABI requires an actual IPropertyValue interface pointer.
        // A boxed managed float or an IInspectable pointer has a different ABI.
        IntPtr property; Guid id=new Guid("4BD682DD-7554-40E9-9A9B-82654EDE7E62"); int hr=Marshal.QueryInterface(boxed,ref id,out property); Marshal.Release(boxed); Marshal.ThrowExceptionForHR(hr); return property;
    }
    public static IntPtr BoxSingle(float value) { IntPtr factory=PropertyValueFactory(); IntPtr vtable=Marshal.ReadIntPtr(factory); var create=(CreateSingleDelegate)Marshal.GetDelegateForFunctionPointer(Marshal.ReadIntPtr(vtable,14*IntPtr.Size),typeof(CreateSingleDelegate)); IntPtr boxed; Marshal.ThrowExceptionForHR(create(factory,value,out boxed)); return PropertyValueInterface(boxed); }
    public static IntPtr BoxUInt32(uint value) { IntPtr factory=PropertyValueFactory(); IntPtr vtable=Marshal.ReadIntPtr(factory); var create=(CreateUInt32Delegate)Marshal.GetDelegateForFunctionPointer(Marshal.ReadIntPtr(vtable,11*IntPtr.Size),typeof(CreateUInt32Delegate)); IntPtr boxed; Marshal.ThrowExceptionForHR(create(factory,value,out boxed)); return PropertyValueInterface(boxed); }
    [StructLayout(LayoutKind.Sequential)] public struct QueueOptions { public uint Size, ThreadType, ApartmentType; }
    [DllImport("CoreMessaging.dll")] public static extern int CreateDispatcherQueueController(QueueOptions options, out IntPtr controller);
    [DllImport("dwmapi.dll")] public static extern int DwmSetWindowAttribute(IntPtr hwnd, int attribute, ref int value, int size);
    [DllImport("dwmapi.dll")] public static extern int DwmGetWindowAttribute(IntPtr hwnd, int attribute, out int value, int size);
    [DllImport("dwmapi.dll")] public static extern int DwmExtendFrameIntoClientArea(IntPtr hwnd, ref Margins margins);
    [StructLayout(LayoutKind.Sequential)] public struct Margins { public int Left, Right, Top, Bottom; }
    [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hwnd,int command);
}

class Evidence {
    public static string Directory = AppDomain.CurrentDomain.BaseDirectory;
    public static void Log(string text) { Console.Error.WriteLine(DateTime.UtcNow.ToString("o") + " " + text); }
}
