using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using StartMe.Models;

namespace StartMe.Services;

public class StartupManager
{
    private readonly StartupRegistryService _registryService;
    private readonly StartupFolderService _folderService;
    private readonly ProcessLauncher _launcher;

    public List<StartupEntry> Entries { get; private set; } = new();

    public StartupManager(
        StartupRegistryService registryService,
        StartupFolderService folderService,
        ProcessLauncher launcher)
    {
        _registryService = registryService;
        _folderService = folderService;
        _launcher = launcher;
    }

    public void EnumerateAll()
    {
        Entries = new List<StartupEntry>();
        Entries.AddRange(_registryService.GetEntries(Microsoft.Win32.RegistryHive.CurrentUser));
        Entries.AddRange(_registryService.GetEntries(Microsoft.Win32.RegistryHive.LocalMachine));
        Entries.AddRange(_registryService.GetEntries(Microsoft.Win32.RegistryHive.LocalMachine, wow64: true));
        Entries.AddRange(_folderService.GetEntries(isCommon: false));
        Entries.AddRange(_folderService.GetEntries(isCommon: true));
    }

    public void SuppressAll()
    {
        foreach (var entry in Entries)
        {
            if (entry.Source is StartupSource.RegistryHKCU or StartupSource.RegistryHKLM)
                _registryService.Suppress(entry);
            else
                _folderService.Suppress(entry);
        }
    }

    public void EnableAll()
    {
        foreach (var entry in Entries)
        {
            if (entry.Source is StartupSource.RegistryHKCU or StartupSource.RegistryHKLM)
                _registryService.Enable(entry);
            else
                _folderService.Enable(entry);
        }
    }

    public async Task LaunchAllSequentially(CancellationToken ct)
    {
        foreach (var entry in Entries)
        {
            ct.ThrowIfCancellationRequested();

            entry.Status = LaunchStatus.Launching;

            try
            {
                var error = await _launcher.LaunchAsync(entry, ct);
                if (error == null)
                {
                    entry.Status = LaunchStatus.Launched;
                }
                else
                {
                    entry.ErrorMessage = error;
                    entry.Status = LaunchStatus.Failed;
                }
            }
            catch (OperationCanceledException)
            {
                entry.ErrorMessage = "Launch cancelled";
                entry.Status = LaunchStatus.Failed;
                throw;
            }
            catch (Exception ex)
            {
                entry.ErrorMessage = ex.Message;
                entry.Status = LaunchStatus.Failed;
            }
        }
    }
}
