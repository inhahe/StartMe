using System.Diagnostics;
using System.Security.Principal;

namespace StartMe.Services;

public static class ElevationHelper
{
    public static bool IsAdmin()
    {
        using var identity = WindowsIdentity.GetCurrent();
        var principal = new WindowsPrincipal(identity);
        return principal.IsInRole(WindowsBuiltInRole.Administrator);
    }

    public static bool RelaunchAsAdmin(string[] args)
    {
        var exePath = Process.GetCurrentProcess().MainModule?.FileName;
        if (exePath == null) return false;

        var psi = new ProcessStartInfo
        {
            FileName = exePath,
            Arguments = string.Join(" ", args),
            Verb = "runas",
            UseShellExecute = true
        };

        try
        {
            var proc = Process.Start(psi);
            return proc != null;
        }
        catch
        {
            // User cancelled UAC
            return false;
        }
    }
}
