using System.ComponentModel;
using System.Runtime.CompilerServices;

namespace StartMe.Models;

public class StartupEntry : INotifyPropertyChanged
{
    private LaunchStatus _status = LaunchStatus.Pending;
    private string _errorMessage = string.Empty;

    public string Name { get; set; } = string.Empty;
    public string Command { get; set; } = string.Empty;
    public string ExecutablePath { get; set; } = string.Empty;
    public string Arguments { get; set; } = string.Empty;
    public StartupSource Source { get; set; }
    public bool RequiresAdmin { get; set; }
    public bool IsWow64 { get; set; }

    public LaunchStatus Status
    {
        get => _status;
        set
        {
            if (_status != value)
            {
                _status = value;
                OnPropertyChanged();
            }
        }
    }

    public string ErrorMessage
    {
        get => _errorMessage;
        set
        {
            if (_errorMessage != value)
            {
                _errorMessage = value;
                OnPropertyChanged();
                OnPropertyChanged(nameof(HasError));
            }
        }
    }

    public bool HasError => !string.IsNullOrEmpty(_errorMessage);

    public event PropertyChangedEventHandler? PropertyChanged;

    private void OnPropertyChanged([CallerMemberName] string? name = null)
        => PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));
}
