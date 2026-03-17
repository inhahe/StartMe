using System.Diagnostics;
using System.Reflection;
using Microsoft.Win32;

namespace StartMe.Services;

public static class ScheduledTaskInstaller
{
    private const string TaskName = "StartMe";
    private const string RunKeyPath = @"Software\Microsoft\Windows\CurrentVersion\Run";

    public static bool Install()
    {
        var exePath = Process.GetCurrentProcess().MainModule?.FileName
            ?? Assembly.GetExecutingAssembly().Location;

        try
        {
            using var key = Registry.CurrentUser.CreateSubKey(RunKeyPath, writable: true);
            if (key == null) return false;
            key.SetValue(TaskName, $"\"{exePath}\" --launch");
            return true;
        }
        catch
        {
            return false;
        }
    }

    public static bool Uninstall()
    {
        try
        {
            using var key = Registry.CurrentUser.OpenSubKey(RunKeyPath, writable: true);
            if (key == null) return true;
            key.DeleteValue(TaskName, throwOnMissingValue: false);
            return true;
        }
        catch
        {
            return false;
        }
    }
}
