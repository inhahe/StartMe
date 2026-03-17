using System;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using StartMe.Services;
using StartMe.ViewModels;

namespace StartMe;

public partial class App : Application
{
    protected override async void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);

        var args = e.Args.Select(a => a.ToLowerInvariant()).ToArray();

        var registryService = new StartupRegistryService();
        var folderService = new StartupFolderService(registryService);
        var launcher = new ProcessLauncher();
        var manager = new StartupManager(registryService, folderService, launcher);

        if (args.Contains("--install"))
        {
            // Elevate if not admin
            if (!ElevationHelper.IsAdmin())
            {
                if (ElevationHelper.RelaunchAsAdmin(e.Args))
                {
                    Shutdown(0);
                    return;
                }
                // User cancelled UAC — continue without admin
            }

            manager.EnumerateAll();

            if (!ScheduledTaskInstaller.Install())
            {
                MessageBox.Show("Failed to register startup entry.",
                    "StartMe", MessageBoxButton.OK, MessageBoxImage.Error);
                Shutdown(1);
                return;
            }

            manager.SuppressAll();
            MessageBox.Show(
                $"StartMe installed.\n{manager.Entries.Count} startup items will be managed.\n\nStartup programs will launch sequentially on next logon.",
                "StartMe", MessageBoxButton.OK, MessageBoxImage.Information);
            Shutdown(0);
            return;
        }

        if (args.Contains("--uninstall"))
        {
            // Elevate if not admin
            if (!ElevationHelper.IsAdmin())
            {
                if (ElevationHelper.RelaunchAsAdmin(e.Args))
                {
                    Shutdown(0);
                    return;
                }
            }

            manager.EnumerateAll();
            manager.EnableAll();
            ScheduledTaskInstaller.Uninstall();
            MessageBox.Show("StartMe uninstalled.\nAll startup items have been re-enabled.",
                "StartMe", MessageBoxButton.OK, MessageBoxImage.Information);
            Shutdown(0);
            return;
        }

        // Default: --launch mode
        manager.EnumerateAll();

        if (manager.Entries.Count == 0)
        {
            Shutdown(0);
            return;
        }

        // Suppress any new entries discovered since install
        manager.SuppressAll();

        var viewModel = new MainViewModel(manager.Entries);
        var window = new MainWindow { DataContext = viewModel };
        window.Show();

        var cts = new CancellationTokenSource();

        try
        {
            await manager.LaunchAllSequentially(cts.Token);
        }
        catch (OperationCanceledException) { }

        viewModel.StatusText = "All done.";

        await Task.Delay(2500);
        await window.FadeOutAndClose();

        Shutdown(0);
    }
}
