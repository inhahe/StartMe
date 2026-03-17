using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Runtime.CompilerServices;
using StartMe.Models;

namespace StartMe.ViewModels;

public class MainViewModel : INotifyPropertyChanged
{
    private string _statusText = "Preparing...";
    private int _launchedCount;
    private int _totalCount;

    public ObservableCollection<StartupEntry> Entries { get; }

    public string StatusText
    {
        get => _statusText;
        set { _statusText = value; OnPropertyChanged(); }
    }

    public MainViewModel(List<StartupEntry> entries)
    {
        Entries = new ObservableCollection<StartupEntry>(entries);
        _totalCount = entries.Count;

        foreach (var entry in Entries)
            entry.PropertyChanged += OnEntryStatusChanged;
    }

    private void OnEntryStatusChanged(object? sender, PropertyChangedEventArgs e)
    {
        if (e.PropertyName != nameof(StartupEntry.Status)) return;

        var entry = (StartupEntry)sender!;
        if (entry.Status == LaunchStatus.Launching)
        {
            _launchedCount++;
            StatusText = $"Launching {_launchedCount} of {_totalCount}...";
        }
        else if (entry.Status == LaunchStatus.Launched ||
                 entry.Status == LaunchStatus.Failed ||
                 entry.Status == LaunchStatus.Skipped)
        {
            if (_launchedCount >= _totalCount)
                StatusText = "All done.";
        }
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    private void OnPropertyChanged([CallerMemberName] string? name = null)
        => PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));
}
