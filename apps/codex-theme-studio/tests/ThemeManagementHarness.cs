using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Text;
using System.Threading;

namespace CodexThemeStudio.Desktop
{
    internal sealed class EngineCommandResult
    {
        public int ExitCode;
        public string StandardOutput;
        public string StandardError;
    }

    internal static class ThemeManagementHarness
    {
        private static void Main()
        {
            string root = Path.Combine(Path.GetTempPath(), "codex-theme-management-" + Guid.NewGuid().ToString("N"));
            string stateRoot = Path.Combine(root, "state");
            string engineRoot = Path.Combine(root, "engine");
            try
            {
                WriteTheme(Path.Combine(engineRoot, "presets", "immersive-dark"), "immersive-dark");
                WriteTheme(Path.Combine(engineRoot, "presets", "custom-theme"), "custom-theme");
                string validImage = Path.Combine(root, "valid.png");
                string invalidImage = Path.Combine(root, "invalid.png");
                WriteImage(validImage, 1600, 900);
                WriteImage(invalidImage, 320, 180);

                using (NativeThemeEngine engine = new NativeThemeEngine(stateRoot, engineRoot))
                {
                    EngineCommandResult invalid = engine.ExecuteAsync(
                        new[] { "set-background", "custom-theme", invalidImage },
                        CancellationToken.None,
                        TimeSpan.FromSeconds(10)).GetAwaiter().GetResult();
                    Assert(invalid.ExitCode != 0, "Small background must be rejected.");

                    EngineCommandResult updated = engine.ExecuteAsync(
                        new[] { "set-background", "custom-theme", validImage },
                        CancellationToken.None,
                        TimeSpan.FromSeconds(10)).GetAwaiter().GetResult();
                    Assert(updated.ExitCode == 0, "Valid background update failed: " + updated.StandardError);
                    string customRoot = Path.Combine(stateRoot, "themes", "custom-theme");
                    string metadata = File.ReadAllText(Path.Combine(customRoot, "theme.json"), Encoding.UTF8);
                    Assert(metadata.Contains("assets/local-background.png"), "Theme metadata was not updated.");
                    Assert(File.Exists(Path.Combine(customRoot, "assets", "local-background.png")), "Local background was not copied.");

                    File.WriteAllText(Path.Combine(stateRoot, "paused"), "paused", new UTF8Encoding(false));
                    EngineCommandResult currentBackground = engine.ExecuteAsync(
                        new[] { "set-background", "immersive-dark", validImage },
                        CancellationToken.None,
                        TimeSpan.FromSeconds(10)).GetAwaiter().GetResult();
                    Assert(currentBackground.ExitCode == 0, "Paused current theme background update failed: " + currentBackground.StandardError);
                    Assert(File.ReadAllText(Path.Combine(stateRoot, "active-theme", "theme.json"), Encoding.UTF8).Contains("assets/local-background.png"), "Active theme background was not updated.");

                    EngineCommandResult currentDelete = engine.ExecuteAsync(
                        new[] { "delete", "immersive-dark" },
                        CancellationToken.None,
                        TimeSpan.FromSeconds(10)).GetAwaiter().GetResult();
                    Assert(currentDelete.ExitCode != 0, "Current theme deletion must be rejected.");
                    Assert(Directory.Exists(Path.Combine(stateRoot, "themes", "immersive-dark")), "Current theme was removed.");

                    EngineCommandResult deleted = engine.ExecuteAsync(
                        new[] { "delete", "custom-theme" },
                        CancellationToken.None,
                        TimeSpan.FromSeconds(10)).GetAwaiter().GetResult();
                    Assert(deleted.ExitCode == 0, "Theme deletion failed: " + deleted.StandardError);
                    Assert(!Directory.Exists(customRoot), "Deleted theme remains in the theme store.");
                    Assert(Directory.GetDirectories(Path.Combine(stateRoot, "backups", "deleted-themes"), "custom-theme-*").Length == 1, "Recoverable deletion backup is missing.");
                    Assert(File.ReadAllText(Path.Combine(stateRoot, "state.json"), Encoding.UTF8).Contains("custom-theme"), "Deleted theme tombstone is missing.");
                }

                using (NativeThemeEngine engine = new NativeThemeEngine(stateRoot, engineRoot))
                {
                    Assert(!Directory.Exists(Path.Combine(stateRoot, "themes", "custom-theme")), "Deleted bundled theme was restored on restart.");
                }

                Console.WriteLine("PASS: Local background transaction and recoverable theme deletion verified.");
            }
            finally
            {
                if (Directory.Exists(root)) Directory.Delete(root, true);
            }
        }

        private static void WriteTheme(string directory, string id)
        {
            Directory.CreateDirectory(Path.Combine(directory, "assets"));
            string json = "{\"schemaVersion\":2,\"id\":\"" + id + "\",\"name\":\"" + id + "\",\"assets\":{\"homeBackground\":\"assets/home.png\",\"taskBackground\":\"assets/task.png\",\"icons\":{}}}";
            File.WriteAllText(Path.Combine(directory, "theme.json"), json, new UTF8Encoding(false));
            File.WriteAllText(Path.Combine(directory, "preview.html"), "assets/home.png assets/task.png", new UTF8Encoding(false));
        }

        private static void WriteImage(string path, int width, int height)
        {
            using (Bitmap bitmap = new Bitmap(width, height))
            {
                bitmap.SetPixel(0, 0, Color.Black);
                bitmap.Save(path, ImageFormat.Png);
            }
        }

        private static void Assert(bool condition, string message)
        {
            if (!condition) throw new InvalidOperationException(message);
        }
    }
}
