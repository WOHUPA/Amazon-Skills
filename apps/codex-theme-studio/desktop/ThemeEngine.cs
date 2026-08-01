using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using System.Security.Principal;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;

namespace CodexThemeStudio.Desktop
{
    internal sealed class NativeThemeEngine : IDisposable
    {
        private const string AppVersion = "2.7.8";
        private const string CodexAppUserModelId = "OpenAI.Codex_2p2nqsd0c76g0!App";
        private readonly string stateRoot;
        private readonly string engineRoot;
        private readonly JavaScriptSerializer serializer = new JavaScriptSerializer();
        private readonly Mutex operationMutex;
        private readonly object processSync = new object();
        private readonly ThemeCatalog catalog;
        private readonly ThemeBundleManager bundleManager;
        private readonly RecipeThemeCompiler recipeCompiler;
        private Process activeProcess;

        public NativeThemeEngine(string stateRoot, string engineRoot)
        {
            this.stateRoot = Path.GetFullPath(stateRoot);
            this.engineRoot = Path.GetFullPath(engineRoot);
            serializer.MaxJsonLength = 16 * 1024 * 1024;
            string sid = WindowsIdentity.GetCurrent().User.Value;
            operationMutex = new Mutex(false, "Local\\CodexThemeStudio." + sid + ".ThemeEngine");
            EnsureDirectory(this.stateRoot);
            EnsureDirectory(ThemesRoot);
            EnsureDirectory(ActiveThemeRoot);
            EnsureDirectory(BackupsRoot);
            EnsureDirectory(LogsRoot);
            InitializeThemeStore();
            catalog = new ThemeCatalog(this.stateRoot, Directory.GetDirectories(ThemesRoot).Select(Path.GetFileName));
            bundleManager = new ThemeBundleManager(this.stateRoot, ThemesRoot);
            recipeCompiler = new RecipeThemeCompiler(this.engineRoot, ThemesRoot, serializer);
        }

        public bool IsPaused { get { return File.Exists(PauseFile); } }
        public string CurrentThemeId { get { return ReadThemeId(ActiveThemeRoot); } }
        public ThemeCatalog Catalog { get { return catalog; } }

        public bool RequiresCodexRestart()
        {
            Dictionary<string, object> state = ReadState();
            if (TryGetLiveSession(state, false, out ignoredSession)) return false;
            List<Process> processes = FindCodexProcesses();
            try { return processes.Count > 0; }
            finally { foreach (Process process in processes) process.Dispose(); }
        }

        private LiveSession ignoredSession;

        public string GetRuntimeStatus(bool repairWatcher)
        {
            if (IsPaused) return "PAUSED";
            Dictionary<string, object> state = ReadState();
            LiveSession session;
            if (TryGetLiveSession(state, repairWatcher, out session))
                return IsRecordedInjectorRunning(ReadState()) ? "HEALTHY" : "SELF_HEALING";
            List<Process> processes = FindCodexProcesses();
            try { return processes.Count > 0 ? "NEEDS_RESTART" : "OFFLINE"; }
            finally { foreach (Process process in processes) process.Dispose(); }
        }

        public string GetStatusJson(bool repairWatcher)
        {
            Dictionary<string, object> state = ReadState();
            Dictionary<string, object> payload = new Dictionary<string, object> {
                { "status", "COMPLETE" },
                { "runtimeStatus", GetRuntimeStatus(repairWatcher) },
                { "installed", true },
                { "engineVersion", AppVersion },
                { "engine", "dotnet" },
                { "currentThemeId", CurrentThemeId ?? string.Empty },
                { "paused", IsPaused },
                { "watcherRunning", IsRecordedInjectorRunning(state) },
                { "browserId", GetString(state, "browserId") },
                { "port", state != null && state.ContainsKey("port") ? state["port"] : 0 }
            };
            return serializer.Serialize(payload);
        }

        public Task<EngineCommandResult> ExecuteAsync(string[] arguments, CancellationToken cancellationToken, TimeSpan timeout)
        {
            return Task.Run(delegate { return Execute(arguments, cancellationToken, timeout); }, cancellationToken);
        }

        public void CancelActiveOperation()
        {
            lock (processSync)
            {
                try { if (activeProcess != null && !activeProcess.HasExited) activeProcess.Kill(); }
                catch { }
            }
        }

        public void RestoreForUninstall()
        {
            try
            {
                WritePaused(true);
                Dictionary<string, object> state = ReadState();
                LiveSession session;
                if (TryGetLiveSession(state, false, out session))
                {
                    RunNode(session.NodePath, BuildRemoveArguments(session), CancellationToken.None, TimeSpan.FromSeconds(12));
                }
                StopRecordedInjector(state);
            }
            catch { }
        }

        private string GetThemeListJson()
        {
            List<Dictionary<string, object>> themes = new List<Dictionary<string, object>>();
            foreach (string path in Directory.GetDirectories(ThemesRoot))
            {
                string id = Path.GetFileName(path);
                try
                {
                    Dictionary<string, object> metadata = serializer.DeserializeObject(
                        File.ReadAllText(Path.Combine(path, "theme.json"), Encoding.UTF8)) as Dictionary<string, object>;
                    if (metadata == null) continue;
                    themes.Add(new Dictionary<string, object> {
                        { "id", id },
                        { "name", Convert.ToString(metadata["name"]) },
                        { "appearance", Convert.ToString(metadata["appearance"]) },
                        { "seriesId", catalog.GetSeriesId(id) },
                        { "order", catalog.GetThemeOrder(id) },
                        { "current", string.Equals(id, CurrentThemeId, StringComparison.Ordinal) }
                    });
                }
                catch { }
            }
            Dictionary<string, object> payload = new Dictionary<string, object> {
                { "status", "COMPLETE" },
                { "themes", themes.OrderBy(item => Convert.ToInt32(item["order"])).ThenBy(item => Convert.ToString(item["name"])).ToArray() },
                { "series", catalog.GetSeries().Select(item => new Dictionary<string, object> {
                    { "id", item.Id }, { "name", item.Name }, { "order", item.Order }
                }).ToArray() }
            };
            return serializer.Serialize(payload);
        }

        private string Preview(string value)
        {
            if (!string.IsNullOrWhiteSpace(value) &&
                string.Equals(Path.GetExtension(value), ".codextheme", StringComparison.OrdinalIgnoreCase))
            {
                BundlePreview preview = bundleManager.Preview(value);
                return serializer.Serialize(new Dictionary<string, object> {
                    { "status", "COMPLETE" },
                    { "bundleId", preview.BundleId },
                    { "name", preview.Name },
                    { "series", new Dictionary<string, object> { { "id", preview.SeriesId }, { "name", preview.SeriesName } } },
                    { "themeIds", preview.ThemeIds.ToArray() },
                    { "themeCount", preview.ThemeIds.Count },
                    { "conflicts", preview.Conflicts.ToArray() },
                    { "canImport", preview.Conflicts.Count == 0 },
                    { "willActivate", false }
                });
            }
            string selected = ResolveSavedTheme(value);
            ValidateTheme(selected, value);
            return serializer.Serialize(new Dictionary<string, object> {
                { "status", "COMPLETE" },
                { "themeId", value },
                { "seriesId", catalog.GetSeriesId(value) },
                { "themeDir", selected }
            });
        }

        private string ImportBundle(string packagePath)
        {
            BundlePreview imported = bundleManager.Import(packagePath, catalog);
            return serializer.Serialize(new Dictionary<string, object> {
                { "status", "COMPLETE" },
                { "bundleId", imported.BundleId },
                { "seriesId", imported.SeriesId },
                { "themeIds", imported.ThemeIds.ToArray() },
                { "themeCount", imported.ThemeIds.Count },
                { "activationStatus", "NOT_RUN" }
            });
        }

        private string CreateRecipeTheme(string recipePath, string imagePath)
        {
            RecipeCompilation created = recipeCompiler.Create(recipePath, imagePath);
            catalog.AssignImported("ai-recipes", "AI 配方", new[] { created.Id });
            return serializer.Serialize(new Dictionary<string, object> {
                { "status", "COMPLETE" }, { "themeId", created.Id }, { "name", created.Name },
                { "themeDir", created.ThemeDirectory }, { "layoutMappedToNative", created.LayoutMappedToNative },
                { "activationStatus", "NOT_RUN" }
            });
        }

        private EngineCommandResult Execute(string[] arguments, CancellationToken cancellationToken, TimeSpan timeout)
        {
            bool acquired = false;
            try
            {
                try { acquired = operationMutex.WaitOne(TimeSpan.FromSeconds(2)); }
                catch (AbandonedMutexException) { acquired = true; }
                if (!acquired) throw new InvalidOperationException("另一个主题操作正在执行，请稍后再试。");
                cancellationToken.ThrowIfCancellationRequested();

                string command = arguments != null && arguments.Length > 0 ? arguments[0].Trim().ToLowerInvariant() : string.Empty;
                string value = arguments != null && arguments.Length > 1 ? arguments[1] : string.Empty;
                bool allowRestart = arguments != null && arguments.Any(item => string.Equals(item, "-RestartExisting", StringComparison.OrdinalIgnoreCase));
                string output = "COMPLETE";
                if (command == "status") output = GetStatusJson(true);
                else if (command == "list") output = GetThemeListJson();
                else if (command == "preview") output = Preview(value);
                else if (command == "import") output = ImportBundle(value);
                else if (command == "create-recipe") output = CreateRecipeTheme(value, arguments != null && arguments.Length > 2 ? arguments[2] : string.Empty);
                else if (command == "activate") Activate(value, cancellationToken, timeout, allowRestart);
                else if (command == "set-background") SetBackground(value, arguments != null && arguments.Length > 2 ? arguments[2] : string.Empty, cancellationToken, timeout, allowRestart);
                else if (command == "delete") DeleteTheme(value);
                else if (command == "rollback") Rollback(cancellationToken, timeout, allowRestart);
                else if (command == "pause") Pause(cancellationToken, timeout);
                else if (command == "resume") Resume(cancellationToken, timeout, allowRestart);
                else if (command == "verify") Verify(cancellationToken, timeout);
                else if (command == "restore") Pause(cancellationToken, timeout);
                else throw new InvalidOperationException("不支持的 .NET 主题引擎命令：" + command);

                return new EngineCommandResult { ExitCode = 0, StandardOutput = output, StandardError = string.Empty };
            }
            catch (OperationCanceledException) { throw; }
            catch (Exception ex)
            {
                return new EngineCommandResult { ExitCode = 1, StandardOutput = string.Empty, StandardError = ex.Message };
            }
            finally
            {
                if (acquired) operationMutex.ReleaseMutex();
            }
        }

        private void Activate(string id, CancellationToken cancellationToken, TimeSpan timeout, bool allowRestart)
        {
            string selected = ResolveSavedTheme(id);
            ValidateTheme(selected, id);
            string previousId = ReadThemeId(ActiveThemeRoot);
            string previous = Path.Combine(BackupsRoot, "previous-theme");
            ReplaceDirectoryCopy(ActiveThemeRoot, previous);

            try
            {
                ReplaceDirectoryCopy(selected, ActiveThemeRoot);
                WritePaused(false);
                LiveSession session = EnsureLiveSession(cancellationToken, timeout, allowRestart);
                EngineCommandResult apply = RunNode(session.NodePath, BuildApplyArguments(session), cancellationToken, timeout);
                ThrowIfFailed(apply, "应用主题失败");
                UpdateThemeState(id, previousId);
            }
            catch
            {
                if (Directory.Exists(previous))
                {
                    ReplaceDirectoryCopy(previous, ActiveThemeRoot);
                    try
                    {
                        LiveSession session = EnsureLiveSession(CancellationToken.None, TimeSpan.FromSeconds(30), false);
                        RunNode(session.NodePath, BuildApplyArguments(session), CancellationToken.None, TimeSpan.FromSeconds(30));
                    }
                    catch { }
                }
                throw;
            }
        }

        private void Rollback(CancellationToken cancellationToken, TimeSpan timeout, bool allowRestart)
        {
            string previous = Path.Combine(BackupsRoot, "previous-theme");
            if (!File.Exists(Path.Combine(previous, "theme.json")))
            {
                throw new InvalidOperationException("没有可用的上一主题备份。");
            }
            string currentId = ReadThemeId(ActiveThemeRoot);
            string targetId = ReadThemeId(previous);
            string swap = Path.Combine(BackupsRoot, ".rollback-" + Guid.NewGuid().ToString("N"));
            ReplaceDirectoryCopy(ActiveThemeRoot, swap);
            try
            {
                ReplaceDirectoryCopy(previous, ActiveThemeRoot);
                WritePaused(false);
                LiveSession session = EnsureLiveSession(cancellationToken, timeout, allowRestart);
                EngineCommandResult apply = RunNode(session.NodePath, BuildApplyArguments(session), cancellationToken, timeout);
                ThrowIfFailed(apply, "回退主题失败");
                ReplaceDirectoryCopy(swap, previous);
                UpdateThemeState(targetId, currentId);
            }
            catch
            {
                if (Directory.Exists(swap)) ReplaceDirectoryCopy(swap, ActiveThemeRoot);
                throw;
            }
            finally
            {
                DeleteDirectorySafe(swap);
            }
        }

        private void Pause(CancellationToken cancellationToken, TimeSpan timeout)
        {
            WritePaused(true);
            Dictionary<string, object> state = ReadState();
            LiveSession session;
            if (!TryGetLiveSession(state, false, out session)) return;
            EngineCommandResult removal = RunNode(session.NodePath, BuildRemoveArguments(session), cancellationToken, timeout);
            ThrowIfFailed(removal, "恢复官方外观失败");
        }

        private void Resume(CancellationToken cancellationToken, TimeSpan timeout, bool allowRestart)
        {
            WritePaused(false);
            LiveSession session = EnsureLiveSession(cancellationToken, timeout, allowRestart);
            EngineCommandResult apply = RunNode(session.NodePath, BuildApplyArguments(session), cancellationToken, timeout);
            ThrowIfFailed(apply, "重新应用主题失败");
        }

        private void Verify(CancellationToken cancellationToken, TimeSpan timeout)
        {
            Dictionary<string, object> state = ReadState();
            LiveSession session;
            if (!TryGetLiveSession(state, false, out session))
            {
                throw new InvalidOperationException("Codex 主题运行时当前不可连接。");
            }
            List<string> args = BaseArguments(session);
            args.Insert(1, IsPaused ? "--verify-removed" : "--verify");
            args.Add("--timeout-ms"); args.Add("30000");
            EngineCommandResult verify = RunNode(session.NodePath, args, cancellationToken, timeout);
            ThrowIfFailed(verify, "运行时验证失败");
        }

        private void SetBackground(string id, string sourcePath, CancellationToken cancellationToken, TimeSpan timeout, bool allowRestart)
        {
            string selected = ResolveSavedTheme(id);
            string source = ValidateBackgroundSource(sourcePath);
            string extension = GetBackgroundExtension(source);
            string staging = Path.Combine(BackupsRoot, ".background-" + Guid.NewGuid().ToString("N"));
            string savedBackup = Path.Combine(BackupsRoot, ".background-saved-" + Guid.NewGuid().ToString("N"));
            string activeBackup = Path.Combine(BackupsRoot, ".background-active-" + Guid.NewGuid().ToString("N"));
            bool isCurrent = string.Equals(ReadThemeId(ActiveThemeRoot), id, StringComparison.Ordinal);
            bool releaseBackups = false;

            try
            {
                CopyDirectory(selected, staging);
                string assetsDirectory = Path.Combine(staging, "assets");
                EnsureDirectory(assetsDirectory);
                foreach (string oldFile in Directory.GetFiles(assetsDirectory, "local-background.*")) File.Delete(oldFile);

                string relative = "assets/local-background" + extension;
                File.Copy(source, Path.Combine(assetsDirectory, "local-background" + extension), true);
                UpdateBackgroundMetadata(staging, relative);
                ValidateTheme(staging, id);

                ReplaceDirectoryCopy(selected, savedBackup);
                if (isCurrent) ReplaceDirectoryCopy(ActiveThemeRoot, activeBackup);
                try
                {
                    ReplaceDirectoryCopy(staging, selected);
                    if (isCurrent)
                    {
                        ReplaceDirectoryCopy(staging, ActiveThemeRoot);
                        if (!IsPaused)
                        {
                            LiveSession session = EnsureLiveSession(cancellationToken, timeout, allowRestart);
                            EngineCommandResult apply = RunNode(session.NodePath, BuildApplyArguments(session), cancellationToken, timeout);
                            ThrowIfFailed(apply, "更新背景失败");
                        }
                    }
                    releaseBackups = true;
                }
                catch (Exception updateError)
                {
                    try
                    {
                        ReplaceDirectoryCopy(savedBackup, selected);
                        if (isCurrent) ReplaceDirectoryCopy(activeBackup, ActiveThemeRoot);
                        releaseBackups = true;
                    }
                    catch (Exception restoreError)
                    {
                        throw new InvalidOperationException(
                            "背景更新失败且自动恢复未完成；原主题备份已保留在 " + savedBackup + "。",
                            new AggregateException(updateError, restoreError));
                    }
                    if (isCurrent && !IsPaused)
                    {
                        try
                        {
                            LiveSession session = EnsureLiveSession(CancellationToken.None, TimeSpan.FromSeconds(30), false);
                            RunNode(session.NodePath, BuildApplyArguments(session), CancellationToken.None, TimeSpan.FromSeconds(30));
                        }
                        catch { }
                    }
                    throw;
                }
            }
            finally
            {
                DeleteDirectorySafe(staging);
                if (releaseBackups)
                {
                    DeleteDirectorySafe(savedBackup);
                    DeleteDirectorySafe(activeBackup);
                }
            }
        }

        private void DeleteTheme(string id)
        {
            string selected = ResolveSavedTheme(id);
            if (string.Equals(ReadThemeId(ActiveThemeRoot), id, StringComparison.Ordinal))
                throw new InvalidOperationException("当前正在使用的主题不能删除，请先切换到其他主题。");

            string deletedRoot = Path.Combine(BackupsRoot, "deleted-themes");
            EnsureDirectory(deletedRoot);
            string archive = Path.Combine(deletedRoot, id + "-" + DateTime.UtcNow.ToString("yyyyMMddHHmmss") + "-" + Guid.NewGuid().ToString("N").Substring(0, 8));
            string previous = Path.Combine(BackupsRoot, "previous-theme");
            string previousArchive = Path.Combine(archive, "previous-theme");
            bool movedPrevious = false;

            Directory.Move(selected, archive);
            try
            {
                Dictionary<string, object> state = ReadState() ?? new Dictionary<string, object>(StringComparer.OrdinalIgnoreCase);
                HashSet<string> deletedIds = GetDeletedThemeIds(state);
                deletedIds.Add(id);
                state["deletedThemeIds"] = deletedIds.OrderBy(delegate(string value) { return value; }, StringComparer.Ordinal).ToArray();
                if (string.Equals(ReadThemeId(previous), id, StringComparison.Ordinal))
                {
                    Directory.Move(previous, previousArchive);
                    movedPrevious = true;
                    state["previousThemeId"] = string.Empty;
                }
                state["studioVersion"] = AppVersion;
                WriteState(state);
            }
            catch
            {
                if (movedPrevious && Directory.Exists(previousArchive)) Directory.Move(previousArchive, previous);
                if (!Directory.Exists(selected) && Directory.Exists(archive)) Directory.Move(archive, selected);
                throw;
            }
        }

        private string ValidateBackgroundSource(string sourcePath)
        {
            if (string.IsNullOrWhiteSpace(sourcePath)) throw new InvalidOperationException("请选择本地 PNG 或 JPEG 背景图片。");
            string source = Path.GetFullPath(sourcePath);
            if (!File.Exists(source)) throw new FileNotFoundException("背景图片不存在。", source);
            if ((File.GetAttributes(source) & FileAttributes.ReparsePoint) != 0) throw new IOException("背景图片不能是链接或重解析点。");
            if (new FileInfo(source).Length > 80L * 1024L * 1024L) throw new InvalidDataException("背景图片不能超过 80 MB。");

            using (System.Drawing.Image image = System.Drawing.Image.FromFile(source))
            {
                bool supported = image.RawFormat.Guid == System.Drawing.Imaging.ImageFormat.Png.Guid ||
                    image.RawFormat.Guid == System.Drawing.Imaging.ImageFormat.Jpeg.Guid;
                if (!supported) throw new InvalidDataException("背景图片必须是 PNG 或 JPEG 格式。");
                double ratio = image.Width / (double)image.Height;
                if (image.Width < 1600 || image.Height < 900 || Math.Abs(ratio - (16.0 / 9.0)) > 0.03)
                    throw new InvalidDataException("背景图片必须至少为 1600×900，并接近 16:9。");
                if (image.Width > 7680 || image.Height > 4320)
                    throw new InvalidDataException("背景图片最大支持 7680×4320。");
            }
            return source;
        }

        private static string GetBackgroundExtension(string source)
        {
            using (System.Drawing.Image image = System.Drawing.Image.FromFile(source))
            {
                return image.RawFormat.Guid == System.Drawing.Imaging.ImageFormat.Png.Guid ? ".png" : ".jpg";
            }
        }

        private void UpdateBackgroundMetadata(string themeDirectory, string relativePath)
        {
            string metadataPath = Path.Combine(themeDirectory, "theme.json");
            Dictionary<string, object> metadata = serializer.DeserializeObject(File.ReadAllText(metadataPath, Encoding.UTF8)) as Dictionary<string, object>;
            if (metadata == null) throw new InvalidDataException("theme.json 不是有效对象。");
            Dictionary<string, object> assets = metadata.ContainsKey("assets") ? metadata["assets"] as Dictionary<string, object> : null;
            if (assets == null) throw new InvalidDataException("theme.json 缺少 assets 对象。");
            string oldHome = assets.ContainsKey("homeBackground") ? Convert.ToString(assets["homeBackground"]) : string.Empty;
            string oldTask = assets.ContainsKey("taskBackground") ? Convert.ToString(assets["taskBackground"]) : string.Empty;
            assets["homeBackground"] = relativePath;
            assets["taskBackground"] = relativePath;
            WriteUtf8Atomic(metadataPath, serializer.Serialize(metadata) + Environment.NewLine);

            string previewPath = Path.Combine(themeDirectory, "preview.html");
            if (File.Exists(previewPath))
            {
                string preview = File.ReadAllText(previewPath, Encoding.UTF8);
                if (!string.IsNullOrEmpty(oldHome)) preview = preview.Replace(oldHome, relativePath);
                if (!string.IsNullOrEmpty(oldTask)) preview = preview.Replace(oldTask, relativePath);
                WriteUtf8Atomic(previewPath, preview);
            }
        }

        private LiveSession EnsureLiveSession(CancellationToken cancellationToken, TimeSpan timeout, bool allowRestart)
        {
            Dictionary<string, object> state = ReadState();
            LiveSession session;
            if (TryGetLiveSession(state, true, out session)) return session;

            StopRecordedInjector(state);
            List<Process> codexProcesses = FindCodexProcesses();
            if (codexProcesses.Count > 0 && !allowRestart)
            {
                foreach (Process process in codexProcesses) process.Dispose();
                throw new InvalidOperationException("NEEDS_RESTART：Codex 正在运行但没有可恢复的 CDP 连接；请在 Studio 中确认后重启。");
            }
            if (allowRestart)
            {
                foreach (Process process in codexProcesses)
                {
                    cancellationToken.ThrowIfCancellationRequested();
                    try { process.Kill(); process.WaitForExit(10000); }
                    catch (Exception ex) { throw new InvalidOperationException("无法安全重启 Codex：" + ex.Message); }
                    finally { process.Dispose(); }
                }
            }

            int port = SelectAvailablePort(9335);
            uint launchedPid = PackageLauncher.Launch(CodexAppUserModelId,
                "--remote-debugging-address=127.0.0.1 --remote-debugging-port=" + port);
            if (launchedPid == 0) throw new InvalidOperationException("Windows 未返回 Codex 启动进程。");

            DateTime deadline = DateTime.UtcNow.AddSeconds(Math.Min(45, Math.Max(15, timeout.TotalSeconds)));
            CdpIdentity identity = null;
            while (DateTime.UtcNow < deadline)
            {
                cancellationToken.ThrowIfCancellationRequested();
                identity = ReadCdpIdentity(port);
                if (identity != null) break;
                Thread.Sleep(350);
            }
            if (identity == null) throw new TimeoutException("Codex 未在 45 秒内建立本机主题连接。");

            string codexPath = FindCodexExecutablePath();
            if (string.IsNullOrEmpty(codexPath)) throw new InvalidOperationException("无法验证已启动的 Codex 程序路径。");
            string nodePath = ResolveNodePath(state);
            string injector = InjectorPath;
            if (!File.Exists(injector)) throw new FileNotFoundException("缺少主题渲染器。", injector);

            Process watcher = StartWatcher(nodePath, port, identity.BrowserId, codexPath);
            Dictionary<string, object> newState = new Dictionary<string, object>(StringComparer.OrdinalIgnoreCase);
            newState["schemaVersion"] = 4;
            newState["platform"] = "windows";
            newState["engine"] = "dotnet";
            newState["port"] = port;
            newState["injectorPid"] = watcher.Id;
            newState["injectorStartedAt"] = watcher.StartTime.ToUniversalTime().ToString("o");
            newState["injectorPath"] = injector;
            newState["nodePath"] = nodePath;
            newState["codexExe"] = codexPath;
            newState["codexPackageRoot"] = GetPackageRoot(codexPath);
            newState["codexPackageFullName"] = Path.GetFileName(GetPackageRoot(codexPath));
            newState["codexPackageFamilyName"] = "OpenAI.Codex_2p2nqsd0c76g0";
            newState["codexVersion"] = GetCodexVersion(codexPath);
            newState["browserId"] = identity.BrowserId;
            newState["themeDir"] = ActiveThemeRoot;
            newState["pauseFile"] = PauseFile;
            newState["currentThemeId"] = ReadThemeId(ActiveThemeRoot);
            newState["previousThemeId"] = ReadThemeId(Path.Combine(BackupsRoot, "previous-theme"));
            newState["studioVersion"] = AppVersion;
            newState["createdAt"] = DateTime.UtcNow.ToString("o");
            WriteState(newState);

            Thread.Sleep(600);
            if (watcher.HasExited) throw new InvalidOperationException(".NET 引擎启动主题渲染器失败，请查看日志目录。");
            return new LiveSession { Port = port, BrowserId = identity.BrowserId, NodePath = nodePath, CodexVersion = Convert.ToString(newState["codexVersion"]) };
        }

        private bool TryGetLiveSession(Dictionary<string, object> state, bool ensureWatcher, out LiveSession session)
        {
            session = null;
            if (state == null) return false;
            int port;
            if (!TryGetInt(state, "port", out port) || port < 1024 || port > 65535) return false;
            string browserId = GetString(state, "browserId");
            Guid parsed;
            if (!Guid.TryParse(browserId, out parsed)) return false;
            CdpIdentity identity = ReadCdpIdentity(port);
            if (identity == null || !string.Equals(identity.BrowserId, browserId, StringComparison.OrdinalIgnoreCase)) return false;

            string nodePath;
            try { nodePath = ResolveNodePath(state); }
            catch { return false; }
            string codexPath = GetString(state, "codexExe");
            string codexVersion = GetCodexVersion(codexPath);
            if (string.IsNullOrEmpty(codexVersion)) codexVersion = GetString(state, "codexVersion");
            bool watcherCompatible = IsRecordedInjectorRunning(state) &&
                string.Equals(GetString(state, "engine"), "dotnet", StringComparison.OrdinalIgnoreCase) &&
                string.Equals(GetString(state, "nodePath"), nodePath, StringComparison.OrdinalIgnoreCase) &&
                string.Equals(GetString(state, "codexVersion"), codexVersion, StringComparison.OrdinalIgnoreCase);
            session = new LiveSession
            {
                Port = port,
                BrowserId = browserId,
                NodePath = nodePath,
                CodexVersion = codexVersion
            };
            if (ensureWatcher)
            {
                // Upgrade legacy live sessions in place so diagnostics always
                // describe the actual .NET engine and bundled renderer in use.
                state["schemaVersion"] = 4;
                state["engine"] = "dotnet";
                state["studioVersion"] = AppVersion;
                state["nodePath"] = nodePath;
                state["nodeVersion"] = FileVersionInfo.GetVersionInfo(nodePath).ProductVersion ?? "unknown";
                state["codexVersion"] = codexVersion;
            }
            if (ensureWatcher && !watcherCompatible)
            {
                StopRecordedInjector(state);
                Process watcher = StartWatcher(nodePath, port, browserId, codexPath);
                state["injectorPid"] = watcher.Id;
                state["injectorStartedAt"] = watcher.StartTime.ToUniversalTime().ToString("o");
            }
            if (ensureWatcher) WriteState(state);
            return true;
        }

        private Process StartWatcher(string nodePath, int port, string browserId, string codexPath)
        {
            string version = string.IsNullOrEmpty(codexPath) || !File.Exists(codexPath)
                ? "unknown" : GetCodexVersion(codexPath);
            List<string> args = new List<string> {
                InjectorPath, "--watch", "--port", port.ToString(), "--browser-id", browserId,
                "--theme-dir", ActiveThemeRoot, "--pause-file", PauseFile, "--codex-version", version
            };
            ProcessStartInfo start = CreateProcessStartInfo(nodePath, args, false);
            Process watcher = Process.Start(start);
            if (watcher == null) throw new InvalidOperationException("无法启动主题渲染器。");
            return watcher;
        }

        private EngineCommandResult RunNode(string nodePath, List<string> arguments, CancellationToken cancellationToken, TimeSpan timeout)
        {
            Process process = new Process();
            process.StartInfo = CreateProcessStartInfo(nodePath, arguments, true);
            process.Start();
            lock (processSync) activeProcess = process;
            Task<string> stdout = process.StandardOutput.ReadToEndAsync();
            Task<string> stderr = process.StandardError.ReadToEndAsync();
            DateTime deadline = DateTime.UtcNow.Add(timeout);
            try
            {
                while (!process.WaitForExit(120))
                {
                    if (cancellationToken.IsCancellationRequested)
                    {
                        try { process.Kill(); } catch { }
                        throw new OperationCanceledException(cancellationToken);
                    }
                    if (DateTime.UtcNow >= deadline)
                    {
                        try { process.Kill(); } catch { }
                        throw new TimeoutException("主题操作超时，已停止且保留可恢复状态。");
                    }
                }
                return new EngineCommandResult {
                    ExitCode = process.ExitCode,
                    StandardOutput = stdout.GetAwaiter().GetResult(),
                    StandardError = stderr.GetAwaiter().GetResult()
                };
            }
            finally
            {
                lock (processSync) { if (ReferenceEquals(activeProcess, process)) activeProcess = null; }
                process.Dispose();
            }
        }

        private ProcessStartInfo CreateProcessStartInfo(string fileName, IList<string> arguments, bool redirect)
        {
            ProcessStartInfo start = new ProcessStartInfo();
            start.FileName = fileName;
            start.Arguments = string.Join(" ", arguments.Select(QuoteArgument).ToArray());
            start.UseShellExecute = false;
            start.CreateNoWindow = true;
            start.WindowStyle = ProcessWindowStyle.Hidden;
            start.RedirectStandardOutput = redirect;
            start.RedirectStandardError = redirect;
            if (redirect)
            {
                // Node always emits UTF-8. Explicit decoding prevents Chinese
                // theme names and validation messages from becoming mojibake.
                start.StandardOutputEncoding = new UTF8Encoding(false, true);
                start.StandardErrorEncoding = new UTF8Encoding(false, true);
            }
            return start;
        }

        private List<string> BuildApplyArguments(LiveSession session)
        {
            List<string> args = BaseArguments(session);
            args.Insert(1, "--once");
            args.Add("--theme-dir"); args.Add(ActiveThemeRoot);
            args.Add("--pause-file"); args.Add(PauseFile);
            args.Add("--codex-version"); args.Add(session.CodexVersion ?? "unknown");
            args.Add("--timeout-ms"); args.Add("30000");
            return args;
        }

        private List<string> BuildRemoveArguments(LiveSession session)
        {
            List<string> args = BaseArguments(session);
            args.Insert(1, "--remove");
            args.Add("--theme-dir"); args.Add(ActiveThemeRoot);
            args.Add("--timeout-ms"); args.Add("12000");
            return args;
        }

        private List<string> BaseArguments(LiveSession session)
        {
            return new List<string> { InjectorPath, "--port", session.Port.ToString(), "--browser-id", session.BrowserId };
        }

        private CdpIdentity ReadCdpIdentity(int port)
        {
            try
            {
                HttpWebRequest request = (HttpWebRequest)WebRequest.Create("http://127.0.0.1:" + port + "/json/version");
                request.Proxy = null;
                request.Timeout = 700;
                request.ReadWriteTimeout = 700;
                using (HttpWebResponse response = (HttpWebResponse)request.GetResponse())
                using (StreamReader reader = new StreamReader(response.GetResponseStream(), Encoding.UTF8))
                {
                    Dictionary<string, object> json = serializer.DeserializeObject(reader.ReadToEnd()) as Dictionary<string, object>;
                    if (json == null) return null;
                    string socket = json.ContainsKey("webSocketDebuggerUrl") ? Convert.ToString(json["webSocketDebuggerUrl"]) : string.Empty;
                    const string marker = "/devtools/browser/";
                    int index = socket.IndexOf(marker, StringComparison.OrdinalIgnoreCase);
                    if (index < 0) return null;
                    string id = socket.Substring(index + marker.Length).Trim('/');
                    Guid parsed;
                    return Guid.TryParse(id, out parsed) ? new CdpIdentity { BrowserId = id } : null;
                }
            }
            catch { return null; }
        }

        private int SelectAvailablePort(int preferred)
        {
            for (int port = preferred; port <= preferred + 100; port++)
            {
                TcpListener listener = null;
                try
                {
                    listener = new TcpListener(IPAddress.Loopback, port);
                    listener.Start();
                    return port;
                }
                catch (SocketException) { }
                finally { if (listener != null) listener.Stop(); }
            }
            throw new InvalidOperationException("9335-9435 范围内没有可用的本机端口。");
        }

        private string ResolveNodePath(Dictionary<string, object> state)
        {
            string bundled = Path.Combine(engineRoot, "runtime", "node.exe");
            if (File.Exists(bundled)) return bundled;
            string recorded = GetString(state, "nodePath");
            if (!string.IsNullOrEmpty(recorded) && File.Exists(recorded)) return recorded;
            string path = Environment.GetEnvironmentVariable("PATH") ?? string.Empty;
            foreach (string part in path.Split(Path.PathSeparator))
            {
                try
                {
                    string candidate = Path.Combine(part.Trim(), "node.exe");
                    if (File.Exists(candidate)) return candidate;
                }
                catch { }
            }
            throw new FileNotFoundException("未找到内置 Node.js 运行时；请重新安装 Theme Studio。");
        }

        private List<Process> FindCodexProcesses()
        {
            List<Process> result = new List<Process>();
            foreach (Process process in Process.GetProcessesByName("ChatGPT"))
            {
                try
                {
                    string path = process.MainModule.FileName;
                    if (IsCodexPath(path)) result.Add(process); else process.Dispose();
                }
                catch { process.Dispose(); }
            }
            return result;
        }

        private string FindCodexExecutablePath()
        {
            List<Process> processes = FindCodexProcesses();
            try
            {
                foreach (Process process in processes)
                {
                    try { return process.MainModule.FileName; }
                    catch { }
                }
                return null;
            }
            finally { foreach (Process process in processes) process.Dispose(); }
        }

        private static bool IsCodexPath(string path)
        {
            if (string.IsNullOrWhiteSpace(path)) return false;
            string normalized = path.Replace('/', '\\');
            return normalized.IndexOf("\\WindowsApps\\OpenAI.Codex_", StringComparison.OrdinalIgnoreCase) >= 0 &&
                normalized.EndsWith("\\app\\ChatGPT.exe", StringComparison.OrdinalIgnoreCase);
        }

        private static string GetPackageRoot(string codexPath)
        {
            DirectoryInfo directory = new FileInfo(codexPath).Directory;
            if (directory != null && string.Equals(directory.Name, "app", StringComparison.OrdinalIgnoreCase) && directory.Parent != null)
                return directory.Parent.FullName;
            return string.Empty;
        }

        private static string GetCodexVersion(string codexPath)
        {
            if (string.IsNullOrWhiteSpace(codexPath) || !File.Exists(codexPath)) return string.Empty;
            string packageName = Path.GetFileName(GetPackageRoot(codexPath));
            const string prefix = "OpenAI.Codex_";
            if (!string.IsNullOrEmpty(packageName) && packageName.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
            {
                string remainder = packageName.Substring(prefix.Length);
                int separator = remainder.IndexOf('_');
                string candidate = separator > 0 ? remainder.Substring(0, separator) : remainder;
                Version parsed;
                if (Version.TryParse(candidate, out parsed)) return candidate;
            }
            return FileVersionInfo.GetVersionInfo(codexPath).ProductVersion ?? string.Empty;
        }

        private void StopRecordedInjector(Dictionary<string, object> state)
        {
            int pid;
            if (!TryGetInt(state, "injectorPid", out pid) || pid <= 0) return;
            try
            {
                Process process = Process.GetProcessById(pid);
                try { process.Kill(); process.WaitForExit(5000); }
                finally { process.Dispose(); }
            }
            catch { }
        }

        private bool IsRecordedInjectorRunning(Dictionary<string, object> state)
        {
            int pid;
            if (!TryGetInt(state, "injectorPid", out pid) || pid <= 0) return false;
            try
            {
                using (Process process = Process.GetProcessById(pid)) return !process.HasExited;
            }
            catch { return false; }
        }

        private string ResolveSavedTheme(string id)
        {
            if (string.IsNullOrWhiteSpace(id) || id.Length > 80 || id.Any(delegate(char c) { return !(char.IsLetterOrDigit(c) || c == '-' || c == '_' || c == '.'); }))
                throw new InvalidOperationException("主题 ID 不合法。");
            string path = Path.GetFullPath(Path.Combine(ThemesRoot, id));
            string prefix = ThemesRoot.TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
            if (!path.StartsWith(prefix, StringComparison.OrdinalIgnoreCase) || !Directory.Exists(path))
                throw new DirectoryNotFoundException("未找到指定主题：" + id);
            return path;
        }

        private void InitializeThemeStore()
        {
            string presets = Path.Combine(engineRoot, "presets");
            if (!Directory.Exists(presets)) return;
            HashSet<string> deletedIds = GetDeletedThemeIds(ReadState());
            foreach (string preset in Directory.GetDirectories(presets))
            {
                string metadata = Path.Combine(preset, "theme.json");
                if (!File.Exists(metadata)) continue;
                if (deletedIds.Contains(Path.GetFileName(preset))) continue;
                string destination = Path.Combine(ThemesRoot, Path.GetFileName(preset));
                if (!Directory.Exists(destination)) CopyDirectory(preset, destination);
            }
            if (!File.Exists(Path.Combine(ActiveThemeRoot, "theme.json")))
            {
                string preferred = Path.Combine(ThemesRoot, "immersive-dark");
                string first = Directory.Exists(preferred) ? preferred : Directory.GetDirectories(ThemesRoot).FirstOrDefault();
                if (!string.IsNullOrEmpty(first)) ReplaceDirectoryCopy(first, ActiveThemeRoot);
            }
        }

        private void ValidateTheme(string path, string expectedId)
        {
            AssertNoReparse(path);
            ThemePackageValidator.Validate(path, expectedId, serializer);
        }

        private string ReadThemeId(string directory)
        {
            try
            {
                string metadataPath = Path.Combine(directory, "theme.json");
                Dictionary<string, object> metadata = serializer.DeserializeObject(File.ReadAllText(metadataPath, Encoding.UTF8)) as Dictionary<string, object>;
                return metadata != null && metadata.ContainsKey("id") ? Convert.ToString(metadata["id"]) : string.Empty;
            }
            catch { return string.Empty; }
        }

        private void ReplaceDirectoryCopy(string source, string destination)
        {
            if (!Directory.Exists(source)) throw new DirectoryNotFoundException(source);
            AssertNoReparse(source);
            string staging = destination + ".staging-" + Guid.NewGuid().ToString("N");
            string backup = destination + ".backup-" + Guid.NewGuid().ToString("N");
            CopyDirectory(source, staging);
            try
            {
                if (Directory.Exists(destination)) Directory.Move(destination, backup);
                Directory.Move(staging, destination);
                DeleteDirectorySafe(backup);
            }
            catch
            {
                if (!Directory.Exists(destination) && Directory.Exists(backup)) Directory.Move(backup, destination);
                throw;
            }
            finally { DeleteDirectorySafe(staging); }
        }

        private static void CopyDirectory(string source, string destination)
        {
            Directory.CreateDirectory(destination);
            foreach (string file in Directory.GetFiles(source)) File.Copy(file, Path.Combine(destination, Path.GetFileName(file)), true);
            foreach (string child in Directory.GetDirectories(source))
            {
                FileAttributes attributes = File.GetAttributes(child);
                if ((attributes & FileAttributes.ReparsePoint) != 0) throw new IOException("主题目录不能包含链接或重解析点。");
                CopyDirectory(child, Path.Combine(destination, Path.GetFileName(child)));
            }
        }

        private void UpdateThemeState(string currentId, string previousId)
        {
            Dictionary<string, object> state = ReadState() ?? new Dictionary<string, object>(StringComparer.OrdinalIgnoreCase);
            state["currentThemeId"] = currentId ?? string.Empty;
            state["previousThemeId"] = previousId ?? string.Empty;
            state["studioVersion"] = AppVersion;
            state["engine"] = "dotnet";
            WriteState(state);
        }

        private Dictionary<string, object> ReadState()
        {
            try
            {
                if (!File.Exists(StatePath)) return null;
                return serializer.DeserializeObject(File.ReadAllText(StatePath, Encoding.UTF8)) as Dictionary<string, object>;
            }
            catch { return null; }
        }

        private static HashSet<string> GetDeletedThemeIds(Dictionary<string, object> state)
        {
            HashSet<string> ids = new HashSet<string>(StringComparer.Ordinal);
            if (state == null || !state.ContainsKey("deletedThemeIds")) return ids;
            Array values = state["deletedThemeIds"] as Array;
            if (values == null) return ids;
            foreach (object value in values)
            {
                string id = Convert.ToString(value);
                if (!string.IsNullOrWhiteSpace(id)) ids.Add(id);
            }
            return ids;
        }

        private void WriteState(Dictionary<string, object> state)
        {
            WriteUtf8Atomic(StatePath, serializer.Serialize(state) + Environment.NewLine);
        }

        private void WritePaused(bool paused)
        {
            if (paused) WriteUtf8Atomic(PauseFile, "paused" + Environment.NewLine);
            else { try { if (File.Exists(PauseFile)) File.Delete(PauseFile); } catch { } }
        }

        private static void WriteUtf8Atomic(string path, string content)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            string temp = path + ".tmp-" + Guid.NewGuid().ToString("N");
            File.WriteAllText(temp, content, new UTF8Encoding(false));
            if (File.Exists(path)) File.Replace(temp, path, null); else File.Move(temp, path);
        }

        private static void AssertNoReparse(string path)
        {
            DirectoryInfo current = new DirectoryInfo(Path.GetFullPath(path));
            while (current != null)
            {
                if (current.Exists && (current.Attributes & FileAttributes.ReparsePoint) != 0)
                    throw new IOException("受管主题路径不能包含链接或重解析点。");
                current = current.Parent;
            }
        }

        private static void EnsureDirectory(string path) { if (!Directory.Exists(path)) Directory.CreateDirectory(path); }
        private static void DeleteDirectorySafe(string path) { try { if (Directory.Exists(path)) Directory.Delete(path, true); } catch { } }

        private static string QuoteArgument(string value)
        {
            if (value == null) return "\"\"";
            return "\"" + value.Replace("\"", "\\\"") + "\"";
        }

        private static void ThrowIfFailed(EngineCommandResult result, string action)
        {
            if (result.ExitCode == 0) return;
            string detail = DescribeProcessFailure(result);
            throw new InvalidOperationException(action + (detail.Length == 0 ? "。" : "：" + detail));
        }

        private static string DescribeProcessFailure(EngineCommandResult result)
        {
            string error = (result.StandardError ?? string.Empty).Trim();
            if (error.Length > 0) return LimitMessage(error);
            string output = (result.StandardOutput ?? string.Empty).Trim();
            if (output.Length == 0) return string.Empty;
            try
            {
                JavaScriptSerializer parser = new JavaScriptSerializer { MaxJsonLength = 16 * 1024 * 1024 };
                Dictionary<string, object> root = parser.DeserializeObject(output) as Dictionary<string, object>;
                object[] targets = root != null && root.ContainsKey("targets") ? root["targets"] as object[] : null;
                HashSet<string> details = new HashSet<string>(StringComparer.Ordinal);
                if (targets != null)
                {
                    foreach (Dictionary<string, object> target in targets.OfType<Dictionary<string, object>>())
                    {
                        if (target.ContainsKey("error") && target["error"] != null)
                            details.Add(Convert.ToString(target["error"]));
                        Dictionary<string, object> verification = target.ContainsKey("result")
                            ? target["result"] as Dictionary<string, object> : null;
                        Array failures = verification != null && verification.ContainsKey("verificationFailures")
                            ? verification["verificationFailures"] as Array : null;
                        if (failures != null)
                            foreach (object failure in failures) details.Add(Convert.ToString(failure));
                    }
                }
                if (details.Count > 0)
                    return "运行时校验未通过（" + string.Join("、", details.OrderBy(value => value, StringComparer.Ordinal)) + "）。";
            }
            catch (ArgumentException) { }
            catch (InvalidOperationException) { }
            return LimitMessage(output);
        }

        private static string LimitMessage(string value)
        {
            string normalized = value.Replace("\r\n", "\n").Replace('\r', '\n').Trim();
            return normalized.Length <= 600 ? normalized : normalized.Substring(0, 600) + "…";
        }

        private static string GetString(Dictionary<string, object> state, string key)
        {
            return state != null && state.ContainsKey(key) && state[key] != null ? Convert.ToString(state[key]) : string.Empty;
        }

        private static bool TryGetInt(Dictionary<string, object> state, string key, out int value)
        {
            value = 0;
            return state != null && state.ContainsKey(key) && int.TryParse(Convert.ToString(state[key]), out value);
        }

        private string ThemesRoot { get { return Path.Combine(stateRoot, "themes"); } }
        private string ActiveThemeRoot { get { return Path.Combine(stateRoot, "active-theme"); } }
        private string BackupsRoot { get { return Path.Combine(stateRoot, "backups"); } }
        private string LogsRoot { get { return Path.Combine(stateRoot, "logs"); } }
        private string PauseFile { get { return Path.Combine(stateRoot, "paused"); } }
        private string StatePath { get { return Path.Combine(stateRoot, "state.json"); } }
        private string InjectorPath { get { return Path.Combine(engineRoot, "scripts", "injector.mjs"); } }

        public void Dispose()
        {
            CancelActiveOperation();
            operationMutex.Dispose();
        }

        private sealed class LiveSession
        {
            public int Port;
            public string BrowserId;
            public string NodePath;
            public string CodexVersion;
        }

        private sealed class CdpIdentity { public string BrowserId; }

        [ComImport, Guid("45ba127d-10a8-46ea-8ab7-56ea9078943c")]
        private class ApplicationActivationManager { }

        [ComImport, InterfaceType(ComInterfaceType.InterfaceIsIUnknown), Guid("2e941141-7f97-4756-ba1d-9decde894a3d")]
        private interface IApplicationActivationManager
        {
            [PreserveSig]
            int ActivateApplication([MarshalAs(UnmanagedType.LPWStr)] string appUserModelId,
                [MarshalAs(UnmanagedType.LPWStr)] string arguments, uint options, out uint processId);
        }

        private static class PackageLauncher
        {
            public static uint Launch(string appUserModelId, string arguments)
            {
                IApplicationActivationManager manager = (IApplicationActivationManager)new ApplicationActivationManager();
                try
                {
                    uint processId;
                    int result = manager.ActivateApplication(appUserModelId, arguments ?? string.Empty, 0, out processId);
                    Marshal.ThrowExceptionForHR(result);
                    return processId;
                }
                finally { if (Marshal.IsComObject(manager)) Marshal.FinalReleaseComObject(manager); }
            }
        }
    }
}
