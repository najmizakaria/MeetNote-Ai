using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

internal static class Launcher
{
    [STAThread]
    private static void Main()
    {
        string directory = AppDomain.CurrentDomain.BaseDirectory;
        string python = Path.Combine(directory, "_runtime", "pythonw.exe");
        string script = Path.Combine(directory, "desktop_app.py");
        try
        {
            if (!File.Exists(python) || !File.Exists(script))
            {
                throw new FileNotFoundException("Keep MeetNote AI.exe in the project folder with _runtime and desktop_app.py.");
            }

            using (Process app = Process.Start(new ProcessStartInfo
            {
                FileName = python,
                Arguments = "-E -s -B \"desktop_app.py\"",
                WorkingDirectory = directory,
                UseShellExecute = false,
                CreateNoWindow = true
            }))
            {
                if (app == null)
                {
                    throw new InvalidOperationException("The desktop window could not start.");
                }
            }
        }
        catch (Exception error)
        {
            MessageBox.Show(error.Message, "MeetNote AI", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }
}
