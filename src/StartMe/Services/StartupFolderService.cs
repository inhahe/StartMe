using System;
using System.Collections.Generic;
using System.IO;
using Microsoft.Win32;
using StartMe.Models;

namespace StartMe.Services;

public class StartupFolderService
{
    private readonly StartupRegistryService _registryService;

    public StartupFolderService(StartupRegistryService registryService)
    {
        _registryService = registryService;
    }

    public List<StartupEntry> GetEntries(bool isCommon)
    {
        var entries = new List<StartupEntry>();
        var folder = isCommon
            ? Environment.GetFolderPath(Environment.SpecialFolder.CommonStartup)
            : Environment.GetFolderPath(Environment.SpecialFolder.Startup);

        if (string.IsNullOrEmpty(folder) || !Directory.Exists(folder))
            return entries;

        var source = isCommon ? StartupSource.CommonStartupFolder : StartupSource.UserStartupFolder;

        foreach (var file in Directory.GetFiles(folder))
        {
            var ext = Path.GetExtension(file).ToLowerInvariant();
            string exePath;
            string arguments;
            string name = Path.GetFileNameWithoutExtension(file);

            if (ext == ".lnk")
            {
                (exePath, arguments) = ResolveShortcut(file);
                if (string.IsNullOrWhiteSpace(exePath)) continue;
            }
            else if (ext == ".exe")
            {
                exePath = file;
                arguments = string.Empty;
            }
            else
            {
                // .bat, .cmd, .vbs, etc. — launch via shell
                exePath = file;
                arguments = string.Empty;
            }

            entries.Add(new StartupEntry
            {
                Name = name,
                Command = $"\"{exePath}\" {arguments}".Trim(),
                ExecutablePath = exePath,
                Arguments = arguments,
                Source = source,
                RequiresAdmin = isCommon
            });
        }

        return entries;
    }

    public void Suppress(StartupEntry entry)
    {
        var linkFileName = GetLinkFileName(entry);
        var hive = entry.Source == StartupSource.CommonStartupFolder
            ? RegistryHive.LocalMachine
            : RegistryHive.CurrentUser;
        _registryService.SuppressFolderEntry(linkFileName, hive);
    }

    public void Enable(StartupEntry entry)
    {
        var linkFileName = GetLinkFileName(entry);
        var hive = entry.Source == StartupSource.CommonStartupFolder
            ? RegistryHive.LocalMachine
            : RegistryHive.CurrentUser;
        _registryService.EnableFolderEntry(linkFileName, hive);
    }

    private static string GetLinkFileName(StartupEntry entry)
    {
        // The StartupApproved\StartupFolder key uses the .lnk filename
        var folder = entry.Source == StartupSource.CommonStartupFolder
            ? Environment.GetFolderPath(Environment.SpecialFolder.CommonStartup)
            : Environment.GetFolderPath(Environment.SpecialFolder.Startup);

        // Find the actual link file for this entry
        if (Directory.Exists(folder))
        {
            foreach (var file in Directory.GetFiles(folder, "*.lnk"))
            {
                if (Path.GetFileNameWithoutExtension(file)
                    .Equals(entry.Name, StringComparison.OrdinalIgnoreCase))
                {
                    return Path.GetFileName(file);
                }
            }
        }

        return entry.Name + ".lnk";
    }

    private static (string targetPath, string arguments) ResolveShortcut(string lnkPath)
    {
        try
        {
            var shellType = Type.GetTypeFromProgID("WScript.Shell");
            if (shellType == null) return (string.Empty, string.Empty);

            dynamic shell = Activator.CreateInstance(shellType)!;
            var shortcut = shell.CreateShortcut(lnkPath);
            string target = shortcut.TargetPath ?? string.Empty;
            string args = shortcut.Arguments ?? string.Empty;

            System.Runtime.InteropServices.Marshal.FinalReleaseComObject(shortcut);
            System.Runtime.InteropServices.Marshal.FinalReleaseComObject(shell);

            return (target, args);
        }
        catch
        {
            return (string.Empty, string.Empty);
        }
    }
}
