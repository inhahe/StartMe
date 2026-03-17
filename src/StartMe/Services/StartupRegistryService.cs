using System;
using System.Collections.Generic;
using System.IO;
using Microsoft.Win32;
using StartMe.Models;

namespace StartMe.Services;

public class StartupRegistryService
{
    private const string RunKeyPath = @"Software\Microsoft\Windows\CurrentVersion\Run";
    private const string RunKeyPathWow64 = @"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run";
    private const string ApprovedKeyPath = @"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run";
    private const string ApprovedKeyPathWow64 = @"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run32";
    private const string ApprovedFolderKeyPath = @"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder";

    public List<StartupEntry> GetEntries(RegistryHive hive, bool wow64 = false)
    {
        var entries = new List<StartupEntry>();
        var isHKLM = hive == RegistryHive.LocalMachine;
        var source = isHKLM ? StartupSource.RegistryHKLM : StartupSource.RegistryHKCU;

        try
        {
            var keyPath = wow64 ? RunKeyPathWow64 : RunKeyPath;
            using var baseKey = RegistryKey.OpenBaseKey(hive, RegistryView.Default);
            using var runKey = baseKey.OpenSubKey(keyPath);
            if (runKey == null) return entries;

            foreach (var name in runKey.GetValueNames())
            {
                var command = runKey.GetValue(name)?.ToString();
                if (string.IsNullOrWhiteSpace(command)) continue;

                // Skip our own entry
                if (name.Equals("StartMe", StringComparison.OrdinalIgnoreCase)) continue;

                var (exePath, args) = ParseCommand(command);

                entries.Add(new StartupEntry
                {
                    Name = name,
                    Command = command,
                    ExecutablePath = exePath,
                    Arguments = args,
                    Source = source,
                    RequiresAdmin = isHKLM,
                    IsWow64 = wow64
                });
            }
        }
        catch (System.Security.SecurityException)
        {
            // No access to HKLM — silently skip
        }
        catch (UnauthorizedAccessException)
        {
            // No access — silently skip
        }

        return entries;
    }

    public void Suppress(StartupEntry entry)
    {
        WriteApprovedValue(entry, disabled: true);
    }

    public void Enable(StartupEntry entry)
    {
        WriteApprovedValue(entry, disabled: false);
    }

    public void SuppressFolderEntry(string linkFileName, RegistryHive hive)
    {
        WriteApprovedFolderValue(linkFileName, hive, disabled: true);
    }

    public void EnableFolderEntry(string linkFileName, RegistryHive hive)
    {
        WriteApprovedFolderValue(linkFileName, hive, disabled: false);
    }

    private void WriteApprovedValue(StartupEntry entry, bool disabled)
    {
        var hive = entry.Source == StartupSource.RegistryHKLM
            ? RegistryHive.LocalMachine
            : RegistryHive.CurrentUser;

        try
        {
            var approvedPath = entry.IsWow64 ? ApprovedKeyPathWow64 : ApprovedKeyPath;
            using var baseKey = RegistryKey.OpenBaseKey(hive, RegistryView.Default);
            using var approvedKey = baseKey.CreateSubKey(approvedPath, writable: true);
            if (approvedKey == null) return;

            var data = BuildApprovedBytes(disabled);
            approvedKey.SetValue(entry.Name, data, RegistryValueKind.Binary);
        }
        catch (UnauthorizedAccessException) { }
        catch (System.Security.SecurityException) { }
    }

    private void WriteApprovedFolderValue(string linkFileName, RegistryHive hive, bool disabled)
    {
        try
        {
            using var baseKey = RegistryKey.OpenBaseKey(hive, RegistryView.Default);
            using var approvedKey = baseKey.CreateSubKey(ApprovedFolderKeyPath, writable: true);
            if (approvedKey == null) return;

            var data = BuildApprovedBytes(disabled);
            approvedKey.SetValue(linkFileName, data, RegistryValueKind.Binary);
        }
        catch (UnauthorizedAccessException) { }
        catch (System.Security.SecurityException) { }
    }

    private static byte[] BuildApprovedBytes(bool disabled)
    {
        var data = new byte[12];
        data[0] = disabled ? (byte)0x03 : (byte)0x02;
        // bytes 1-3 = 0x00
        if (disabled)
        {
            var ft = DateTime.UtcNow.ToFileTimeUtc();
            var ftBytes = BitConverter.GetBytes(ft);
            Array.Copy(ftBytes, 0, data, 4, 8);
        }
        return data;
    }

    public static (string exePath, string arguments) ParseCommand(string command)
    {
        command = Environment.ExpandEnvironmentVariables(command.Trim());

        if (command.StartsWith('"'))
        {
            var endQuote = command.IndexOf('"', 1);
            if (endQuote > 0)
            {
                var exe = command[1..endQuote];
                var args = endQuote + 1 < command.Length
                    ? command[(endQuote + 1)..].TrimStart()
                    : string.Empty;
                return (exe, args);
            }
        }

        // No quotes — find the first space that yields a valid file
        var spaceIdx = command.IndexOf(' ');
        if (spaceIdx < 0)
            return (command, string.Empty);

        // Try progressively longer paths
        for (var i = spaceIdx; i >= 0 && i < command.Length; i = command.IndexOf(' ', i + 1))
        {
            var candidate = command[..i];
            if (File.Exists(candidate) || File.Exists(candidate + ".exe"))
                return (candidate, command[(i + 1)..].TrimStart());
        }

        // Fallback: split on first space
        return (command[..spaceIdx], command[(spaceIdx + 1)..].TrimStart());
    }
}
