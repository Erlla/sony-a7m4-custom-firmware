using System;
using System.ComponentModel;
using System.Linq;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

// Windows USB hub control only. No camera protocol or arbitrary IOCTL API.
public static class SonyCameraPortRecovery {
    [DllImport("cfgmgr32.dll", CharSet=CharSet.Unicode)]
    static extern uint CM_Get_Device_Interface_List_SizeW(out uint length, ref Guid guid, string id, uint flags);
    [DllImport("cfgmgr32.dll", CharSet=CharSet.Unicode)]
    static extern uint CM_Get_Device_Interface_ListW(ref Guid guid, string id, [Out] char[] buffer, uint length, uint flags);
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    static extern SafeFileHandle CreateFileW(string name, uint access, uint share, IntPtr security, uint creation, uint attributes, IntPtr template);
    [DllImport("kernel32.dll", SetLastError=true)]
    [return:MarshalAs(UnmanagedType.Bool)]
    static extern bool DeviceIoControl(SafeFileHandle handle, uint code, IntPtr input, uint inputLength,
        IntPtr output, uint outputLength, out uint bytes, IntPtr overlapped);

    static string HubInterface(string parent) {
        if (String.IsNullOrEmpty(parent) || !parent.StartsWith("USB\\", StringComparison.OrdinalIgnoreCase))
            throw new ArgumentException("Expected the inspected USB parent instance");
        Guid guid=new Guid("f18a0e88-c30c-11d0-8815-00a0c906bed8");
        for (int attempt=0;attempt<3;attempt++) {
            uint length, rc=CM_Get_Device_Interface_List_SizeW(out length,ref guid,parent,0);
            if (rc!=0 || length<2 || length>32768) throw new InvalidOperationException("Hub interface size failed: "+rc);
            char[] buffer=new char[length];
            rc=CM_Get_Device_Interface_ListW(ref guid,parent,buffer,length,0);
            if (rc==0x1a) continue;
            if (rc!=0) throw new InvalidOperationException("Hub interface query failed: "+rc);
            string[] paths=new String(buffer).Split(new char[]{'\0'},StringSplitOptions.RemoveEmptyEntries);
            if (paths.Length!=1) throw new InvalidOperationException("Expected exactly one interface for this parent hub");
            return paths[0];
        }
        throw new InvalidOperationException("Hub interface changed during query");
    }

    public static object InspectOrCycle(string parent, uint port, bool cycle) {
        if (port<1 || port>255) throw new ArgumentException("Invalid one-based USB port");
        string path=HubInterface(parent);
        using (SafeFileHandle hub=CreateFileW(path,0x40000000,3,IntPtr.Zero,3,0,IntPtr.Zero)) {
            if (hub.IsInvalid) throw new Win32Exception(Marshal.GetLastWin32Error());
            IntPtr info=Marshal.AllocHGlobal(256);
            try {
                Marshal.Copy(new byte[256],0,info,256);Marshal.WriteInt32(info,(int)port);
                uint bytes;
                // USB_NODE_CONNECTION_INFORMATION_EX, packed Windows USB ABI.
                if (!DeviceIoControl(hub,0x00220448,info,256,info,256,out bytes,IntPtr.Zero))
                    throw new Win32Exception(Marshal.GetLastWin32Error());
                uint vendor=(ushort)Marshal.ReadInt16(info,12), product=(ushort)Marshal.ReadInt16(info,14);
                uint status=(uint)Marshal.ReadInt32(info,31);
                if (bytes<35 || vendor!=0x054c || product!=0x0da5 || Marshal.ReadByte(info,24)!=0 || status!=1)
                    throw new InvalidOperationException("This port is not the connected normal-mode Sony camera");
                uint returned=0;
                if (cycle) {
                    Marshal.Copy(new byte[8],0,info,8);Marshal.WriteInt32(info,(int)port);
                    if (!DeviceIoControl(hub,0x00220444,info,8,info,8,out returned,IntPtr.Zero))
                        throw new Win32Exception(Marshal.GetLastWin32Error());
                }
                return new { parent=parent, hub_interface=path, port=port, vendor=vendor, product=product,
                    connected=true, cycle_requested=cycle, ioctl_succeeded=true, returned_bytes=returned };
            } finally { Marshal.FreeHGlobal(info); }
        }
    }
}
