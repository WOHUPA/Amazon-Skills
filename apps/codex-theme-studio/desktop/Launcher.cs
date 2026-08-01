using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Reflection;
using System.Security.Principal;
using System.Text;
using System.Threading;
using System.Windows.Forms;
using System.Runtime.InteropServices;

[assembly: AssemblyTitle("Codex Theme Studio")]
[assembly: AssemblyDescription("Windows launcher for Codex Theme Studio")]
[assembly: AssemblyCompany("Codex Theme Studio")]
[assembly: AssemblyProduct("Codex Theme Studio")]
[assembly: AssemblyCopyright("Copyright (c) 2026")]
[assembly: AssemblyVersion("2.7.8.0")]
[assembly: AssemblyFileVersion("2.7.8.0")]
[assembly: AssemblyInformationalVersion("2.7.8")]

namespace CodexThemeStudio.Desktop
{
    internal static class Program
    {
        private const string AppVersion = "2.7.8";
        private const string RuntimeResource = "CodexThemeStudio.Runtime.zip";
        private static readonly string StateRoot = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "CodexThemeStudio");
        private static readonly string EngineRoot = Path.Combine(StateRoot, "engine");

        [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
        private static extern int SetCurrentProcessExplicitAppUserModelID(string appId);

        [STAThread]
        private static int Main(string[] args)
        {
            bool prepareUninstall = HasArgument(args, "--prepare-uninstall");
            bool forceInstall = HasArgument(args, "--install-runtime") || HasArgument(args, "--repair");
            string engineCommand = GetArgumentValue(args, "--engine");
            string openPackage = GetArgumentValue(args, "--open-package");
            if (string.IsNullOrWhiteSpace(openPackage) && args.Length == 1 &&
                string.Equals(Path.GetExtension(args[0]), ".codextheme", StringComparison.OrdinalIgnoreCase))
                openPackage = args[0];
            bool background = HasArgument(args, "--background");
            bool noUi = HasArgument(args, "--no-ui") || !string.IsNullOrWhiteSpace(engineCommand);

            try
            {
                try { SetCurrentProcessExplicitAppUserModelID("CodexThemeStudio.Desktop"); } catch { }
                if (prepareUninstall)
                {
                    return PrepareUninstall();
                }

                EnsureRuntime(forceInstall);
                if (!string.IsNullOrWhiteSpace(engineCommand))
                {
                    return RunEngineCommand(args, engineCommand);
                }

                string sid = WindowsIdentity.GetCurrent().User.Value;
                using (Mutex mutex = new Mutex(false, "Local\\CodexThemeStudio." + sid + ".Desktop"))
                using (SingleInstanceChannel channel = new SingleInstanceChannel(sid))
                {
                    bool acquired;
                    try { acquired = mutex.WaitOne(0); }
                    catch (AbandonedMutexException) { acquired = true; }
                    if (!acquired)
                    {
                        channel.TrySend(string.IsNullOrWhiteSpace(openPackage) ? "__SHOW__" : Path.GetFullPath(openPackage), 1200);
                        return 0;
                    }

                    if (noUi)
                    {
                        return 0;
                    }

                    System.Windows.Application application = new System.Windows.Application();
                    application.ShutdownMode = System.Windows.ShutdownMode.OnExplicitShutdown;
                    using (StudioClient client = new StudioClient(StateRoot, EngineRoot))
                    using (StudioTray tray = new StudioTray(client, Path.Combine(EngineRoot, "assets", "studio.ico")))
                    {
                        channel.Start(delegate(string command)
                        {
                            if (command == "__EXIT__") return;
                            client.Window.Dispatcher.BeginInvoke(new Action(delegate
                            {
                                if (command == "__SHOW__") client.ShowAndActivate();
                                else client.OpenPackage(command);
                            }));
                        });
                        application.MainWindow = client.Window;
                        if (!background || !string.IsNullOrWhiteSpace(openPackage)) client.Window.Show();
                        if (!string.IsNullOrWhiteSpace(openPackage)) client.ImportThemeBundle(Path.GetFullPath(openPackage));
                        application.Run();
                    }
                    return 0;
                }
            }
            catch (Exception ex)
            {
                if (!noUi)
                {
                    MessageBox.Show(
                        ex.Message,
                        "Codex Theme Studio",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Error);
                }
                return 1;
            }
        }

        private static bool HasArgument(string[] args, string expected)
        {
            foreach (string arg in args)
            {
                if (string.Equals(arg, expected, StringComparison.OrdinalIgnoreCase))
                {
                    return true;
                }
            }
            return false;
        }

        private static string GetArgumentValue(string[] args, string expected)
        {
            for (int index = 0; index < args.Length - 1; index++)
            {
                if (string.Equals(args[index], expected, StringComparison.OrdinalIgnoreCase))
                {
                    return args[index + 1];
                }
            }
            return string.Empty;
        }

        private static int RunEngineCommand(string[] args, string command)
        {
            string themeId = GetArgumentValue(args, "--theme");
            string packagePath = GetArgumentValue(args, "--package");
            string resultPath = GetArgumentValue(args, "--result-file");
            bool confirmed = HasArgument(args, "--confirm");
            string normalized = command.Trim().ToLowerInvariant();
            string[] supportedCommands = {
                "status", "list", "preview", "import", "create-recipe", "activate", "rollback",
                "pause", "resume", "verify", "restore"
            };
            if (!supportedCommands.Contains(normalized))
            {
                EngineCommandResult unsupported = new EngineCommandResult {
                    ExitCode = 2,
                    StandardOutput = string.Empty,
                    StandardError = "Unsupported engine action: " + command
                };
                WriteEngineResult(resultPath, unsupported);
                return unsupported.ExitCode;
            }
            string[] writeCommands = { "import", "create-recipe", "activate", "rollback", "pause", "resume", "restore" };
            if (writeCommands.Contains(normalized) && !confirmed)
            {
                EngineCommandResult denied = new EngineCommandResult {
                    ExitCode = 2,
                    StandardOutput = string.Empty,
                    StandardError = command + " requires --confirm after explicit user intent."
                };
                WriteEngineResult(resultPath, denied);
                return denied.ExitCode;
            }
            string[] engineArguments;
            if (normalized == "activate")
                engineArguments = confirmed
                    ? new[] { normalized, themeId, "-RestartExisting" }
                    : new[] { normalized, themeId };
            else if (normalized == "preview")
                engineArguments = new[] { normalized, !string.IsNullOrWhiteSpace(packagePath) ? packagePath : themeId };
            else if (normalized == "import")
                engineArguments = new[] { normalized, packagePath };
            else if (normalized == "create-recipe")
                engineArguments = new[] { normalized, GetArgumentValue(args, "--recipe"), GetArgumentValue(args, "--image") };
            else if (confirmed && (normalized == "resume" || normalized == "rollback"))
                engineArguments = new[] { normalized, "-RestartExisting" };
            else engineArguments = new[] { normalized };

            EngineCommandResult result;
            using (NativeThemeEngine engine = new NativeThemeEngine(StateRoot, EngineRoot))
            {
                result = engine.ExecuteAsync(engineArguments, CancellationToken.None, TimeSpan.FromSeconds(45))
                    .GetAwaiter().GetResult();
            }

            WriteEngineResult(resultPath, result);
            return result.ExitCode;
        }

        private static void WriteEngineResult(string resultPath, EngineCommandResult result)
        {
            if (string.IsNullOrWhiteSpace(resultPath)) return;
            string fullPath = Path.GetFullPath(resultPath);
            string parent = Path.GetDirectoryName(fullPath);
            if (!string.IsNullOrEmpty(parent)) Directory.CreateDirectory(parent);
            string json = "{\"engineVersion\":\"" + AppVersion + "\",\"exitCode\":" + result.ExitCode +
                ",\"standardOutput\":\"" + EscapeJson(result.StandardOutput) +
                "\",\"standardError\":\"" + EscapeJson(result.StandardError) + "\"}";
            File.WriteAllText(fullPath, json, new UTF8Encoding(false));
        }

        private static string EscapeJson(string value)
        {
            if (string.IsNullOrEmpty(value)) return string.Empty;
            return value.Replace("\\", "\\\\").Replace("\"", "\\\"")
                .Replace("\r", "\\r").Replace("\n", "\\n").Replace("\t", "\\t");
        }

        private static void EnsureRuntime(bool force)
        {
            string versionFile = Path.Combine(EngineRoot, "assets", "studio-version.txt");
            string clientLayout = Path.Combine(EngineRoot, "assets", "studio-window.xaml");
            if (!force && File.Exists(versionFile) && File.Exists(clientLayout))
            {
                string installedVersion = File.ReadAllText(versionFile, Encoding.UTF8).Trim();
                if (string.Equals(installedVersion, AppVersion, StringComparison.Ordinal))
                {
                    return;
                }
            }

            Directory.CreateDirectory(StateRoot);
            string staging = Path.Combine(StateRoot, ".engine-staging-" + Guid.NewGuid().ToString("N"));
            string backup = Path.Combine(StateRoot, ".engine-backup-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(staging);
            try
            {
                ExtractEmbeddedRuntime(staging);
                if (!File.Exists(Path.Combine(staging, "assets", "studio-window.xaml")) ||
                    !File.Exists(Path.Combine(staging, "scripts", "injector.mjs")))
                    throw new InvalidOperationException("内嵌 Theme Studio 运行时不完整。");

                if (Directory.Exists(EngineRoot)) Directory.Move(EngineRoot, backup);
                Directory.Move(staging, EngineRoot);
                DeleteDirectoryWithRetries(backup, false);
            }
            catch
            {
                if (!Directory.Exists(EngineRoot) && Directory.Exists(backup)) Directory.Move(backup, EngineRoot);
                throw;
            }
            finally
            {
                DeleteDirectoryWithRetries(staging, false);
            }

            if (!File.Exists(clientLayout) || !File.Exists(versionFile))
            {
                throw new InvalidOperationException("Theme Studio 运行时安装后未通过完整性检查。");
            }
        }

        private static void ExtractEmbeddedRuntime(string destinationRoot)
        {
            Assembly assembly = Assembly.GetExecutingAssembly();
            using (Stream resource = assembly.GetManifestResourceStream(RuntimeResource))
            {
                if (resource == null)
                {
                    throw new InvalidOperationException("安装程序缺少内嵌 Theme Studio 运行时。");
                }
                using (ZipArchive archive = new ZipArchive(resource, ZipArchiveMode.Read, false))
                {
                    string rootPrefix = Path.GetFullPath(destinationRoot).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
                    foreach (ZipArchiveEntry entry in archive.Entries)
                    {
                        string relative = entry.FullName.Replace('/', Path.DirectorySeparatorChar);
                        string target = Path.GetFullPath(Path.Combine(destinationRoot, relative));
                        if (!target.StartsWith(rootPrefix, StringComparison.OrdinalIgnoreCase))
                        {
                            throw new InvalidOperationException("内嵌运行时包含越界路径：" + entry.FullName);
                        }
                        if (string.IsNullOrEmpty(entry.Name))
                        {
                            Directory.CreateDirectory(target);
                            continue;
                        }
                        string parent = Path.GetDirectoryName(target);
                        if (!string.IsNullOrEmpty(parent))
                        {
                            Directory.CreateDirectory(parent);
                        }
                        using (Stream input = entry.Open())
                        using (FileStream output = new FileStream(target, FileMode.Create, FileAccess.Write, FileShare.None))
                        {
                            input.CopyTo(output);
                        }
                    }
                }
            }
        }

        private static int PrepareUninstall()
        {
            if (Directory.Exists(EngineRoot))
            {
                try
                {
                    using (NativeThemeEngine engine = new NativeThemeEngine(StateRoot, EngineRoot))
                        engine.RestoreForUninstall();
                }
                catch { /* Uninstall must continue; user data remains recoverable. */ }
            }
            DeleteDirectoryWithRetries(EngineRoot, true);
            return 0;
        }

        private static void DeleteDirectoryWithRetries(string path, bool throwOnFailure)
        {
            if (!Directory.Exists(path))
            {
                return;
            }
            Exception last = null;
            for (int attempt = 0; attempt < 8; attempt++)
            {
                try
                {
                    Directory.Delete(path, true);
                    return;
                }
                catch (Exception ex)
                {
                    last = ex;
                    Thread.Sleep(250 * (attempt + 1));
                }
            }
            if (throwOnFailure && last != null)
            {
                throw new IOException("无法删除 Theme Studio 运行时引擎；用户主题数据未删除。", last);
            }
        }

    }
}
