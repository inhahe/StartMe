using System;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Input;
using System.Windows.Media.Animation;

namespace StartMe;

public partial class MainWindow : Window
{
    public MainWindow()
    {
        InitializeComponent();
    }

    private void Window_MouseLeftButtonDown(object sender, MouseButtonEventArgs e)
    {
        DragMove();
    }

    public async Task FadeOutAndClose()
    {
        var anim = new DoubleAnimation(1.0, 0.0, System.Windows.Duration.Automatic);
        anim.Duration = new Duration(System.TimeSpan.FromMilliseconds(400));

        var tcs = new System.Threading.Tasks.TaskCompletionSource();
        anim.Completed += (_, _) => tcs.SetResult();
        BeginAnimation(OpacityProperty, anim);
        await tcs.Task;
        Close();
    }
}
