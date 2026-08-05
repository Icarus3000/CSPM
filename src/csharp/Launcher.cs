using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
using System.Text;

internal static class CSPMLauncher
{
    // ============================================================
    // WIN32 COM IMPORTS FOR JUMP LISTS
    // ============================================================

    [DllImport("shell32.dll", SetLastError = true)]
    private static extern int SetCurrentProcessExplicitAppUserModelID([MarshalAs(UnmanagedType.LPWStr)] string appId);

    [ComImport]
    [Guid("6332DEBF-87B5-4670-90C0-5E57B408A49E")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface ICustomDestinationList
    {
        void SetAppID([MarshalAs(UnmanagedType.LPWStr)] string pszAppID);
        [PreserveSig]
        int BeginList(out uint pcMaxSlots, ref Guid riid, [MarshalAs(UnmanagedType.Interface)] out object ppv);
        [PreserveSig]
        int AppendCategory([MarshalAs(UnmanagedType.LPWStr)] string pszCategory, [MarshalAs(UnmanagedType.Interface)] object poa);
        [PreserveSig]
        int AppendKnownCategory(int category);
        [PreserveSig]
        int AddUserTasks([MarshalAs(UnmanagedType.Interface)] object poa);
        [PreserveSig]
        int CommitList();
        [PreserveSig]
        int GetRemovedDestinations(ref Guid riid, [MarshalAs(UnmanagedType.Interface)] out object ppv);
        [PreserveSig]
        int DeleteList([MarshalAs(UnmanagedType.LPWStr)] string pszAppID);
        [PreserveSig]
        int AbortList();
    }

    [ComImport]
    [Guid("77F10CF0-3DB5-4966-B520-B7C54FD35ED6")]
    [ClassInterface(ClassInterfaceType.None)]
    private class CDestinationList
    {
    }

    [ComImport]
    [Guid("000214F9-0000-0000-C000-000000000046")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IShellLinkW
    {
        void GetPath([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder pszFile, int cchMaxPath, IntPtr pfd, int fFlags);
        void GetIDList(out IntPtr ppidl);
        void SetIDList(IntPtr pidl);
        void GetDescription([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder pszName, int cchMaxName);
        void SetDescription([MarshalAs(UnmanagedType.LPWStr)] string pszName);
        void GetWorkingDirectory([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder pszDir, int cchMaxPath);
        void SetWorkingDirectory([MarshalAs(UnmanagedType.LPWStr)] string pszDir);
        void GetArguments([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder pszArgs, int cchMaxPath);
        void SetArguments([MarshalAs(UnmanagedType.LPWStr)] string pszArgs);
        void GetHotkey(out short pwHotkey);
        void SetHotkey(short wHotkey);
        void GetShowCmd(out int piShowCmd);
        void SetShowCmd(int iShowCmd);
        void GetIconLocation([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder pszIconPath, int cchIconPath, out int piIcon);
        void SetIconLocation([MarshalAs(UnmanagedType.LPWStr)] string pszIconPath, int iIcon);
        void SetRelativePath([MarshalAs(UnmanagedType.LPWStr)] string pszPathRel, int dwReserved);
        void Resolve(IntPtr hwnd, int fFlags);
        void SetPath([MarshalAs(UnmanagedType.LPWStr)] string pszFile);
    }

    [ComImport]
    [Guid("00021401-0000-0000-C000-000000000046")]
    [ClassInterface(ClassInterfaceType.None)]
    private class CShellLink
    {
    }

    [ComImport]
    [Guid("5632B1A4-E38A-400A-928A-D4CD63230295")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IObjectCollection
    {
        void GetCount(out uint pcObjects);
        void GetAt(uint uiIndex, ref Guid riid, [MarshalAs(UnmanagedType.Interface)] out object ppv);
        void AddObject([MarshalAs(UnmanagedType.Interface)] object punk);
        void AddFromArray([MarshalAs(UnmanagedType.Interface)] object poa);
        void RemoveAt(uint uiIndex);
        void Clear();
    }

    [ComImport]
    [Guid("2D3468C1-36A7-43B6-AC24-D3F02FD9607A")]
    [ClassInterface(ClassInterfaceType.None)]
    private class CEnumerableObjectCollection
    {
    }

    [ComImport]
    [Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IPropertyStore
    {
        void GetCount(out uint cProps);
        void GetAt(uint iProp, out PropertyKey pkey);
        void GetValue(ref PropertyKey pkey, [Out] PropVariant pv);
        void SetValue(ref PropertyKey pkey, [In] PropVariant pv);
        void Commit();
    }

    [StructLayout(LayoutKind.Sequential, Pack = 4)]
    private struct PropertyKey
    {
        public Guid fmtid;
        public uint pid;

        public PropertyKey(Guid fmtid, uint pid)
        {
            this.fmtid = fmtid;
            this.pid = pid;
        }
    }

    [StructLayout(LayoutKind.Explicit)]
    private class PropVariant : IDisposable
    {
        [FieldOffset(0)]
        public ushort vt;
        [FieldOffset(8)]
        public IntPtr ptr;

        public static PropVariant FromString(string val)
        {
            var pv = new PropVariant();
            pv.vt = 31; // VT_LPWSTR
            pv.ptr = Marshal.StringToCoTaskMemUni(val);
            return pv;
        }

        public void Dispose()
        {
            if (ptr != IntPtr.Zero)
            {
                Marshal.FreeCoTaskMem(ptr);
                ptr = IntPtr.Zero;
            }
            vt = 0;
        }
    }

    private static readonly PropertyKey PKEY_Title = new PropertyKey(new Guid("F29F85E0-4FF9-1068-AB91-08002B27B3D9"), 2);
    private static readonly PropertyKey PKEY_AppUserModel_ID = new PropertyKey(new Guid("9F4C6855-37D7-4965-8F05-974021482817"), 5);
    private const string APP_ID = "CSPM.PracticeConsole";

    [DllImport("shell32.dll", SetLastError = true)]
    private static extern void SHChangeNotify(int wEventId, uint uFlags, IntPtr dwItem1, IntPtr dwItem2);

    // ============================================================
    // JUMP LIST REGISTRATION
    // ============================================================

    private static void RegisterJumpList(string exePath)
    {
        try
        {
            SetCurrentProcessExplicitAppUserModelID(APP_ID);

            var customList = (ICustomDestinationList)new CDestinationList();
            customList.SetAppID(APP_ID);

            uint maxSlots;
            Guid iidIObjectArray = new Guid("92CA9DCD-5622-4bba-A805-5E9F541BD8C9");
            object listObj;
            int hr = customList.BeginList(out maxSlots, ref iidIObjectArray, out listObj);
            if (hr != 0) return;

            var collection = (IObjectCollection)listObj;
            string workingDir = Path.GetDirectoryName(exePath);

            // Task 1: Run Clean (Silent)
            var linkClean = (IShellLinkW)new CShellLink();
            linkClean.SetPath(exePath);
            linkClean.SetArguments("--clean");
            linkClean.SetWorkingDirectory(workingDir);
            linkClean.SetDescription("Launches CSPM silently in the background (Clean Mode)");
            linkClean.SetIconLocation(exePath, 0);
            using (var pv = PropVariant.FromString("Run Clean"))
            {
                var store = (IPropertyStore)linkClean;
                PropertyKey key = PKEY_Title;
                store.SetValue(ref key, pv);
                store.Commit();
            }
            collection.AddObject(linkClean);

            // Task 2: Run Verbose (Visible Console)
            var linkVerbose = (IShellLinkW)new CShellLink();
            linkVerbose.SetPath(exePath);
            linkVerbose.SetArguments("--verbose");
            linkVerbose.SetWorkingDirectory(workingDir);
            linkVerbose.SetDescription("Launches CSPM with a visible console window (Verbose Mode)");
            linkVerbose.SetIconLocation(exePath, 0);
            using (var pv = PropVariant.FromString("Run Verbose"))
            {
                var store = (IPropertyStore)linkVerbose;
                PropertyKey key = PKEY_Title;
                store.SetValue(ref key, pv);
                store.Commit();
            }
            collection.AddObject(linkVerbose);

            customList.AddUserTasks(collection);
            customList.CommitList();
        }
        catch (Exception ex)
        {
            // Fail silently on environments that do not support Jump Lists
            Debug.WriteLine("JumpList registration failed: " + ex.Message);
        }
    }

    // ============================================================
    // APPLICATION LAUNCH LOGIC
    // ============================================================

    private static string Quote(string value)
    {
        if (string.IsNullOrEmpty(value))
        {
            return "\"\"";
        }
        if (value.Contains("\""))
        {
            value = value.Replace("\"", "\\\"");
        }
        if (value.Contains(" ") || value.Contains("\t"))
        {
            return "\"" + value + "\"";
        }
        return value;
    }

    private static void FixAllTaskbarShortcuts(string exePath)
    {
        try
        {
            string taskbarFolder = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                @"Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar"
            );

            if (Directory.Exists(taskbarFolder))
            {
                string[] lnkFiles = Directory.GetFiles(taskbarFolder, "*.lnk");
                bool changed = false;
                foreach (var lnkPath in lnkFiles)
                {
                    try
                    {
                        var link = (IShellLinkW)new CShellLink();
                        var persistFile = (IPersistFile)link;
                        persistFile.Load(lnkPath, 0); // STGM_READ

                        var sb = new StringBuilder(260);
                        link.GetPath(sb, sb.Capacity, IntPtr.Zero, 0);
                        string target = sb.ToString();
 
                        if (string.Equals(target, exePath, StringComparison.OrdinalIgnoreCase))
                        {
                            var store = (IPropertyStore)link;
                            using (var pv = PropVariant.FromString(APP_ID))
                            {
                                PropertyKey key = PKEY_AppUserModel_ID;
                                store.SetValue(ref key, pv);
                                store.Commit();
                            }
                            persistFile.Save(lnkPath, true);
                            changed = true;
                        }
                    }
                    catch
                    {
                        // Ignore individual file load/save errors
                    }
                }
 
                if (changed)
                {
                    SHChangeNotify(0x08000000, 0, IntPtr.Zero, IntPtr.Zero); // SHCNE_ASSOCCHANGED
                }
            }
        }
        catch (Exception ex)
        {
            Debug.WriteLine("FixAllTaskbarShortcuts failed: " + ex.Message);
        }
    }

    private static int Main(string[] args)
    {
        string appRoot = AppContext.BaseDirectory;
        string exePath = Process.GetCurrentProcess().MainModule.FileName;

        // Determine if we should run verbose or clean
        bool verboseMode = false;
        bool cleanMode = false;
        if (args != null)
        {
            foreach (var arg in args)
            {
                if (arg.Equals("--verbose", StringComparison.OrdinalIgnoreCase))
                {
                    verboseMode = true;
                }
                else if (arg.Equals("--clean", StringComparison.OrdinalIgnoreCase))
                {
                    cleanMode = true;
                }
            }
        }

        // Only run self-healing and Jump List registration if NOT launched via a task
        if (!verboseMode && !cleanMode)
        {
            // Force self-healing of any misassociated or cached taskbar shortcuts
            FixAllTaskbarShortcuts(exePath);

            // Automatically register or refresh the taskbar Jump List tasks on launch
            RegisterJumpList(exePath);
        }

        string powershellScript = Path.Combine(appRoot, "launch.ps1");
        if (verboseMode && File.Exists(powershellScript))
        {
            var psiPS = new ProcessStartInfo
            {
                FileName = "powershell.exe",
                Arguments = "-NoProfile -ExecutionPolicy Bypass -File " + Quote(powershellScript),
                WorkingDirectory = appRoot,
                UseShellExecute = false,
                CreateNoWindow = false
            };

            if (args != null)
            {
                foreach (var arg in args)
                {
                    if (arg.Equals("--verbose", StringComparison.OrdinalIgnoreCase) ||
                        arg.Equals("--clean", StringComparison.OrdinalIgnoreCase))
                    {
                        continue;
                    }
                    psiPS.Arguments += " " + Quote(arg);
                }
            }

            var process = Process.Start(psiPS);
            if (process != null)
            {
                process.WaitForExit();
            }
            return 0;
        }

        // Setup paths
        string runtimeDir = Path.Combine(appRoot, "runtime");
        // Run clean uses pythonw.exe (no window); run verbose uses python.exe (shows console)
        string pythonExe = Path.Combine(runtimeDir, verboseMode ? "python.exe" : "pythonw.exe");
        string scriptPath = Path.Combine(appRoot, "src", "python", "main.py");
        bool isVenv = false;

        if (!File.Exists(pythonExe))
        {
            // Fallback for development environment: search for .venv_*
            try
            {
                string[] venvDirs = Directory.GetDirectories(appRoot, ".venv_*");
                if (venvDirs.Length > 0)
                {
                    // Use the first matching virtual environment
                    runtimeDir = venvDirs[0];
                    pythonExe = Path.Combine(runtimeDir, "Scripts", verboseMode ? "python.exe" : "pythonw.exe");
                    isVenv = true;
                }
            }
            catch
            {
                // Fall through to standard error check
            }
        }

        if (!File.Exists(pythonExe))
        {
            Console.Error.WriteLine("Python interpreter not found: " + pythonExe);
            return 2;
        }
        if (!File.Exists(scriptPath))
        {
            Console.Error.WriteLine("Entry script not found: " + scriptPath);
            return 3;
        }

        var psi = new ProcessStartInfo
        {
            FileName = pythonExe,
            Arguments = Quote(scriptPath),
            WorkingDirectory = appRoot,
            UseShellExecute = false,
            CreateNoWindow = !verboseMode // Hide console completely when in clean mode
        };

        if (args != null)
        {
            foreach (var arg in args)
            {
                // Skip our custom arguments, pass the rest to python main
                if (arg.Equals("--verbose", StringComparison.OrdinalIgnoreCase) ||
                    arg.Equals("--clean", StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }
                psi.Arguments += " " + Quote(arg);
            }
        }

        if (!isVenv)
        {
            psi.Environment["PYTHONHOME"] = runtimeDir;
        }
        psi.Environment["PYTHONPATH"] = Path.Combine(appRoot, "src", "python");

        string pySideDir = Path.Combine(runtimeDir, "Lib", "site-packages", "PySide6");
        string qtPluginPath = Path.Combine(pySideDir, "plugins");
        string qmlImportPath = Path.Combine(pySideDir, "qml");
        if (Directory.Exists(qtPluginPath))
        {
            psi.Environment["QT_PLUGIN_PATH"] = qtPluginPath;
        }
        if (Directory.Exists(qmlImportPath))
        {
            psi.Environment["QML2_IMPORT_PATH"] = qmlImportPath;
        }

        var pythonProcess = Process.Start(psi);
        if (pythonProcess != null)
        {
            pythonProcess.WaitForExit();
        }
        return 0;
    }
}
