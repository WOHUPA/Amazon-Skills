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
        private static void Main(string[] args)
        {
            if (args.Length != 1) throw new ArgumentException("Repository root is required.");
            string presetRoot = Path.Combine(args[0], "presets", "immersive-dark");
            string root = Path.Combine(Path.GetTempPath(), "codex-theme-management-" + Guid.NewGuid().ToString("N"));
            string stateRoot = Path.Combine(root, "state");
            string engineRoot = Path.Combine(root, "engine");
            try
            {
                WriteTheme(presetRoot, Path.Combine(engineRoot, "presets", "immersive-dark"), "immersive-dark");
                WriteTheme(presetRoot, Path.Combine(engineRoot, "presets", "custom-theme"), "custom-theme");
                string validImage = Path.Combine(root, "中文背景.png");
                string invalidImage = Path.Combine(root, "invalid.png");
                string recipePath = Path.Combine(root, "recipe.json");
                WriteImage(validImage, 1600, 900);
                WriteImage(invalidImage, 320, 180);
                File.WriteAllText(recipePath,
                    "{\"schemaVersion\":1,\"name\":\"配方主题\",\"layout\":\"full-canvas\",\"appearance\":{\"density\":\"normal\"},\"paletteIntent\":{\"appearance\":\"dark\"}}",
                    new UTF8Encoding(false));

                System.Web.Script.Serialization.JavaScriptSerializer serializer = new System.Web.Script.Serialization.JavaScriptSerializer();
                AiThemeJobs jobs = new AiThemeJobs(stateRoot, serializer);
                AiThemeJob job = jobs.Create("深海月光，左侧留白，避免文字和 UI 元素。");
                Assert(File.Exists(Path.Combine(jobs.JobDirectory(job.Id), "prompt.md")), "AI job prompt was not persisted.");
                AiThemeRevision candidate = jobs.AddCandidate(job.Id, recipePath, validImage);
                Assert(candidate.Number == 1, "First AI candidate revision must be v1.");
                Assert(File.Exists(candidate.RecipePath) && File.Exists(candidate.ImagePath), "AI candidate artifacts were not copied into the managed job directory.");
                Assert(jobs.CurrentCandidate(job.Id).Number == 1, "AI job current candidate was not persisted.");

                using (NativeThemeEngine engine = new NativeThemeEngine(stateRoot, engineRoot))
                {
                    EngineCommandResult compiledRecipe = engine.ExecuteAsync(
                        new[] { "create-recipe", recipePath, validImage },
                        CancellationToken.None,
                        TimeSpan.FromSeconds(10)).GetAwaiter().GetResult();
                    Assert(compiledRecipe.ExitCode == 0, "Recipe compilation failed: " + compiledRecipe.StandardError);
                    Assert(compiledRecipe.StandardOutput.Contains("\"activationStatus\":\"NOT_RUN\""), "Recipe compilation must not activate a theme.");
                    Assert(compiledRecipe.StandardOutput.Contains("\"layoutMappedToNative\":true"), "Unsupported recipe layouts must map to native.");

                    EngineCommandResult invalid = engine.ExecuteAsync(
                        new[] { "set-background", "custom-theme", invalidImage },
                        CancellationToken.None,
                        TimeSpan.FromSeconds(10)).GetAwaiter().GetResult();
                    Assert(invalid.ExitCode != 0, "Small background must be rejected.");
                    Assert(invalid.StandardError.Contains("至少为 1600×900"), "Background validation error must remain readable Chinese.");

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

                Console.WriteLine("PASS: Local AI job persistence, background transaction, and recoverable theme deletion verified.");
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine(ex.GetType().FullName);
                Console.Error.WriteLine(ex.Message);
                Console.Error.WriteLine(ex.StackTrace);
                Environment.ExitCode = 1;
            }
            finally
            {
                if (Directory.Exists(root)) Directory.Delete(root, true);
            }
        }

        private static void WriteTheme(string source, string directory, string id)
        {
            CopyDirectory(source, directory);
            string themePath = Path.Combine(directory, "theme.json");
            string json = File.ReadAllText(themePath, Encoding.UTF8)
                .Replace("\"id\": \"immersive-dark\"", "\"id\": \"" + id + "\"")
                .Replace("\"name\": \"沉浸深色\"", "\"name\": \"" + id + "\"");
            File.WriteAllText(themePath, json, new UTF8Encoding(false));
        }

        private static void CopyDirectory(string source, string destination)
        {
            Directory.CreateDirectory(destination);
            foreach (string file in Directory.GetFiles(source))
                File.Copy(file, Path.Combine(destination, Path.GetFileName(file)), true);
            foreach (string child in Directory.GetDirectories(source))
                CopyDirectory(child, Path.Combine(destination, Path.GetFileName(child)));
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
