using System;
using System.Globalization;
using System.Windows.Data;
using System.Windows.Media;
using StartMe.Models;

namespace StartMe.Converters;

public class StatusToColorConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
    {
        if (value is LaunchStatus status)
        {
            return status switch
            {
                LaunchStatus.Pending => new SolidColorBrush(Color.FromRgb(0x66, 0x66, 0x66)),
                LaunchStatus.Launching => new SolidColorBrush(Color.FromRgb(0x1E, 0x90, 0xFF)), // DodgerBlue
                LaunchStatus.Launched => new SolidColorBrush(Color.FromRgb(0x32, 0xCD, 0x32)),  // LimeGreen
                LaunchStatus.Failed => new SolidColorBrush(Color.FromRgb(0xFF, 0x45, 0x00)),    // OrangeRed
                LaunchStatus.Skipped => new SolidColorBrush(Color.FromRgb(0x44, 0x44, 0x44)),
                _ => Brushes.Gray
            };
        }
        return Brushes.Gray;
    }

    public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture)
        => throw new NotSupportedException();
}
