using System;
using System.Diagnostics;
using System.Threading;
using System.Threading.Tasks;
using StartMe.Models;

namespace StartMe.Services;

public class ProcessLauncher
{
    private static readonly TimeSpan InputIdleTimeout = TimeSpan.FromSeconds(15);
    private static readonly TimeSpan CpuSettleTimeout = TimeSpan.FromSeconds(30);
    private static readonly TimeSpan CpuPollInterval = TimeSpan.FromMilliseconds(500);
    private static readonly double CpuThresholdMs = 50; // ms of CPU per poll interval
    private const int SettledChecksRequired = 3;

    public async Task<string?> LaunchAsync(StartupEntry entry, CancellationToken ct)
    {
        var psi = new ProcessStartInfo
        {
            FileName = entry.ExecutablePath,
            Arguments = entry.Arguments,
            UseShellExecute = true
        };

        Process? process;
        try
        {
            process = Process.Start(psi);
        }
        catch (System.ComponentModel.Win32Exception ex)
        {
            return $"Win32 error: {ex.Message}";
        }
        catch (System.IO.FileNotFoundException)
        {
            return $"File not found: {entry.ExecutablePath}";
        }
        catch (Exception ex)
        {
            return ex.Message;
        }

        if (process == null)
            return "Process.Start returned null";

        // If process exits almost immediately (launcher/updater pattern), consider it done
        if (process.WaitForExit(2000))
            return null;

        // Phase 1: WaitForInputIdle for GUI apps
        try
        {
            await Task.Run(() => process.WaitForInputIdle((int)InputIdleTimeout.TotalMilliseconds), ct);
        }
        catch (InvalidOperationException)
        {
            // No message loop (console app, service, etc.) — move to CPU check
        }

        // Phase 2: Wait for CPU usage to settle
        await WaitForCpuSettle(process, ct);

        return null; // null = success, no error
    }

    private static async Task WaitForCpuSettle(Process process, CancellationToken ct)
    {
        var deadline = DateTime.UtcNow + CpuSettleTimeout;
        var settledCount = 0;
        TimeSpan lastCpu;

        try
        {
            lastCpu = process.TotalProcessorTime;
        }
        catch
        {
            // Can't read CPU time (access denied or process exited)
            return;
        }

        while (DateTime.UtcNow < deadline && settledCount < SettledChecksRequired)
        {
            ct.ThrowIfCancellationRequested();
            await Task.Delay(CpuPollInterval, ct);

            try
            {
                if (process.HasExited)
                    return;

                var currentCpu = process.TotalProcessorTime;
                var delta = (currentCpu - lastCpu).TotalMilliseconds;
                lastCpu = currentCpu;

                if (delta < CpuThresholdMs)
                    settledCount++;
                else
                    settledCount = 0;
            }
            catch
            {
                // Process exited or access denied
                return;
            }
        }
    }
}
