using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows;
using System.Windows.Controls;

namespace CodexThemeStudio.Desktop
{
    internal static class UpdateTrust
    {
        public const string UpdaterSha256 = "0000000000000000000000000000000000000000000000000000000000000000";
        public const string VerifierSha256 = "0000000000000000000000000000000000000000000000000000000000000000";
        public static readonly string[] PublicKeys = new string[0];
    }

    internal static class StudioPerformanceHarness
    {
        [STAThread]
        private static int Main(string[] args)
        {
            if (args.Length < 1 || args.Length > 2) throw new ArgumentException("Pass the Theme Studio source root.");
            string engineRoot = Path.GetFullPath(args[0]);
            string stateRoot = Path.Combine(Path.GetTempPath(), "codex-theme-studio-perf-" + Guid.NewGuid().ToString("N"));
            try
            {
                PrepareThemes(stateRoot, Path.Combine(engineRoot, "presets", "clear-light"), 100);
                Application application = new Application { ShutdownMode = ShutdownMode.OnExplicitShutdown };
                Stopwatch timer = Stopwatch.StartNew();
                using (StudioClient client = new StudioClient(stateRoot, engineRoot))
                {
                    client.Window.Show();
                    client.Window.UpdateLayout();
                    timer.Stop();
                    WrapPanel strip = client.Window.FindName("ThemeStrip") as WrapPanel;
                    TextBlock count = client.Window.FindName("ThemeCountLabel") as TextBlock;
                    if (strip == null || strip.Children.Count > 18)
                        throw new InvalidOperationException("Theme card virtualization did not cap the live visual tree.");
                    Match totalMatch = count == null ? Match.Empty : Regex.Match(count.Text, @"总计\s+(\d+)");
                    int loadedThemes;
                    if (!totalMatch.Success || !int.TryParse(totalMatch.Groups[1].Value, out loadedThemes) || loadedThemes < 100)
                        throw new InvalidOperationException("The 100-theme catalog was not loaded.");
                    Console.WriteLine(
                        "{{\"pass\":true,\"themes\":{0},\"liveCards\":{1},\"interactiveMs\":{2}}}",
                        loadedThemes,
                        strip.Children.Count,
                        timer.ElapsedMilliseconds);
                    if (timer.ElapsedMilliseconds > 2500)
                        throw new InvalidOperationException("Cold interactive startup exceeded 2500 ms.");
                    if (args.Length > 1 && string.Equals(args[1], "--idle-120", StringComparison.OrdinalIgnoreCase))
                    {
                        for (int settle = 0; settle < 20; settle++)
                        {
                            PumpDispatcher();
                            Thread.Sleep(100);
                        }
                        Process process = Process.GetCurrentProcess();
                        TimeSpan cpuStart = process.TotalProcessorTime;
                        Stopwatch idleTimer = Stopwatch.StartNew();
                        for (int sample = 0; sample < 1200; sample++)
                        {
                            PumpDispatcher();
                            Thread.Sleep(100);
                        }
                        idleTimer.Stop();
                        process.Refresh();
                        double cpuPercent = (process.TotalProcessorTime - cpuStart).TotalSeconds /
                            (idleTimer.Elapsed.TotalSeconds * Environment.ProcessorCount) * 100.0;
                        Console.WriteLine(
                            "{{\"pass\":true,\"idleSeconds\":{0:0.0},\"averageCpuPercent\":{1:0.0000}}}",
                            idleTimer.Elapsed.TotalSeconds,
                            cpuPercent);
                        if (cpuPercent >= 1.0)
                            throw new InvalidOperationException("Two-minute idle CPU average exceeded 1 percent.");
                    }
                    client.RequestExit();
                }
                return 0;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine(
                    "{{\"pass\":false,\"type\":\"{0}\",\"message\":\"{1}\"}}",
                    ex.GetType().FullName,
                    (ex.Message ?? string.Empty).Replace("\\", "\\\\").Replace("\"", "\\\""));
                return 1;
            }
            finally
            {
                try { if (Directory.Exists(stateRoot)) Directory.Delete(stateRoot, true); }
                catch (Exception cleanupError)
                {
                    Console.Error.WriteLine("Performance harness cleanup warning: " + cleanupError.Message);
                }
            }
        }

        private static void PrepareThemes(string stateRoot, string templateRoot, int count)
        {
            if (!Directory.Exists(templateRoot)) throw new DirectoryNotFoundException(templateRoot);
            string themesRoot = Path.Combine(stateRoot, "themes");
            Directory.CreateDirectory(themesRoot);
            JavaScriptSerializer serializer = new JavaScriptSerializer();
            for (int index = 0; index < count; index++)
            {
                string id = "performance-theme-" + index.ToString("D3");
                string destination = Path.Combine(themesRoot, id);
                CopyDirectory(templateRoot, destination);
                string themePath = Path.Combine(destination, "theme.json");
                Dictionary<string, object> theme = serializer.DeserializeObject(
                    File.ReadAllText(themePath, Encoding.UTF8)) as Dictionary<string, object>;
                theme["id"] = id;
                theme["name"] = "Performance Theme " + index.ToString("D3");
                File.WriteAllText(themePath, serializer.Serialize(theme), new UTF8Encoding(false));
            }
        }

        private static void CopyDirectory(string source, string destination)
        {
            Directory.CreateDirectory(destination);
            foreach (string file in Directory.GetFiles(source))
                File.Copy(file, Path.Combine(destination, Path.GetFileName(file)));
            foreach (string directory in Directory.GetDirectories(source))
                CopyDirectory(directory, Path.Combine(destination, Path.GetFileName(directory)));
        }

        private static void PumpDispatcher()
        {
            System.Windows.Threading.DispatcherFrame frame = new System.Windows.Threading.DispatcherFrame();
            System.Windows.Threading.Dispatcher.CurrentDispatcher.BeginInvoke(
                System.Windows.Threading.DispatcherPriority.Background,
                new System.Windows.Threading.DispatcherOperationCallback(
                    delegate(object state)
                    {
                        ((System.Windows.Threading.DispatcherFrame)state).Continue = false;
                        return null;
                    }),
                frame);
            System.Windows.Threading.Dispatcher.PushFrame(frame);
        }
    }
}
