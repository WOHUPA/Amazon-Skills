using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Markup;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Threading;
using Forms = System.Windows.Forms;
using Ellipse = System.Windows.Shapes.Ellipse;

namespace CodexThemeStudio.Desktop
{
    internal sealed class ThemeItem
    {
        public string Id;
        public string Name;
        public string Appearance;
        public string Layout;
        public string Directory;
        public string BackgroundPath;
        public string SeriesId;
    }

    internal sealed class EngineCommandResult
    {
        public int ExitCode;
        public string StandardOutput;
        public string StandardError;
    }

    internal sealed class StudioClient : IDisposable
    {
        private const string AppVersion = "2.7.8";
        private const int ThemePageSize = 18;
        private readonly string stateRoot;
        private readonly string engineRoot;
        private readonly NativeThemeEngine engine;
        private readonly RuntimeSupervisor supervisor;
        private readonly RuntimeAssetCache assetCache;
        private readonly UpdateService updateService;
        private readonly AiThemeJobs aiJobs;
        private readonly JavaScriptSerializer serializer = new JavaScriptSerializer();
        private readonly List<ThemeItem> themes = new List<ThemeItem>();
        private readonly Dictionary<string, BitmapSource> imageCache = new Dictionary<string, BitmapSource>(StringComparer.OrdinalIgnoreCase);
        private readonly Queue<string> imageCacheOrder = new Queue<string>();
        private readonly object imageCacheSync = new object();
        private readonly DispatcherTimer progressTimer;
        private Window window;
        private ThemeItem selectedTheme;
        private string currentThemeId = string.Empty;
        private string filter = "all";
        private string selectedSeriesId = ThemeCatalog.AllSeriesId;
        private int themePageStart;
        private CancellationTokenSource operationCancellation;
        private DateTime operationStartedAt;
        private bool exitRequested;

        private Border titleBar;
        private Image titleIcon;
        private Button minimizeButton;
        private Button maximizeButton;
        private Button closeButton;
        private Button themesNav;
        private Button aiNav;
        private Button editorNav;
        private Button creatorNav;
        private Button runtimeNav;
        private Button settingsNav;
        private Grid themesPage;
        private Grid aiPage;
        private Grid editorPage;
        private Grid creatorPage;
        private Grid runtimePage;
        private Grid settingsPage;
        private Button createThemeButton;
        private Button importThemeButton;
        private Button recipeThemeButton;
        private Button aiStartButton;
        private TextBox aiPromptBox;
        private TextBlock aiJobStatus;
        private Button aiCompileCandidateButton;
        private Button editorRecipeButton;
        private StackPanel seriesStrip;
        private Button newSeriesButton;
        private Button renameSeriesButton;
        private Button deleteSeriesButton;
        private TextBox searchBox;
        private TextBlock searchHint;
        private Button allFilter;
        private Button darkFilter;
        private Button lightFilter;
        private Grid heroContent;
        private Image heroImage;
        private TextBlock heroName;
        private TextBlock heroMeta;
        private TextBlock heroDescription;
        private Button heroApplyButton;
        private Button heroPreviewButton;
        private Button heroBackgroundButton;
        private Button heroDeleteButton;
        private Button heroMoveButton;
        private TextBlock themeCountLabel;
        private ScrollViewer themeScroll;
        private WrapPanel themeStrip;
        private Button scrollLeftButton;
        private Button scrollRightButton;
        private Border activityDock;
        private ProgressBar busyBar;
        private TextBlock operationTitle;
        private TextBlock progressText;
        private Button cancelOperationButton;
        private Ellipse runtimeDot;
        private TextBlock runtimeLabel;
        private TextBlock currentThemeValue;
        private TextBlock runtimeModeValue;
        private TextBlock runtimeDetailValue;
        private Button pauseButton;
        private Button resumeButton;
        private Button runtimeVerifyButton;
        private Button rollbackButton;
        private Button restoreButton;
        private TextBlock themeStorePath;
        private TextBlock enginePath;
        private TextBlock updateStatus;
        private Button checkUpdateButton;
        private TextBlock creatorThemeCount;

        public StudioClient(string stateRoot, string engineRoot)
        {
            this.stateRoot = stateRoot;
            this.engineRoot = engineRoot;
            engine = new NativeThemeEngine(stateRoot, engineRoot);
            supervisor = new RuntimeSupervisor(engine);
            assetCache = new RuntimeAssetCache(stateRoot);
            updateService = new UpdateService(stateRoot, engineRoot, AppVersion);
            serializer.MaxJsonLength = 16 * 1024 * 1024;
            aiJobs = new AiThemeJobs(stateRoot, serializer);
            LoadWindow();
            BindControls();
            NormalizePageHeaders();
            ConfigureWindow();
            progressTimer = new DispatcherTimer(TimeSpan.FromMilliseconds(200), DispatcherPriority.Normal, UpdateProgress, window.Dispatcher);
            progressTimer.Stop();
            window.Loaded += WindowLoaded;
            supervisor.HealthChanged += SupervisorHealthChanged;
        }

        public Window Window { get { return window; } }
        public bool ExitRequested { get { return exitRequested; } }

        private void LoadWindow()
        {
            string xamlPath = Path.Combine(engineRoot, "assets", "studio-window.xaml");
            if (!File.Exists(xamlPath))
            {
                throw new FileNotFoundException("原生客户端布局文件不存在。", xamlPath);
            }
            using (FileStream stream = new FileStream(xamlPath, FileMode.Open, FileAccess.Read, FileShare.Read))
            {
                window = (Window)XamlReader.Load(stream);
            }
        }

        private T Find<T>(string name) where T : class
        {
            T value = window.FindName(name) as T;
            if (value == null) throw new InvalidOperationException("原生客户端缺少控件：" + name);
            return value;
        }

        private void BindControls()
        {
            titleBar = Find<Border>("TitleBar"); titleIcon = Find<Image>("TitleIcon");
            minimizeButton = Find<Button>("MinimizeButton"); maximizeButton = Find<Button>("MaximizeButton"); closeButton = Find<Button>("CloseButton");
            themesNav = Find<Button>("ThemesNav"); aiNav = Find<Button>("AiNav"); editorNav = Find<Button>("EditorNav"); creatorNav = Find<Button>("CreatorNav"); runtimeNav = Find<Button>("RuntimeNav"); settingsNav = Find<Button>("SettingsNav");
            themesPage = Find<Grid>("ThemesPage"); aiPage = Find<Grid>("AiPage"); editorPage = Find<Grid>("EditorPage"); creatorPage = Find<Grid>("CreatorPage"); runtimePage = Find<Grid>("RuntimePage"); settingsPage = Find<Grid>("SettingsPage");
            createThemeButton = Find<Button>("CreateThemeButton"); importThemeButton = Find<Button>("ImportThemeButton"); recipeThemeButton = Find<Button>("RecipeThemeButton"); searchBox = Find<TextBox>("SearchBox"); searchHint = Find<TextBlock>("SearchHint");
            aiStartButton = Find<Button>("AiStartButton"); aiPromptBox = Find<TextBox>("AiPromptBox"); aiJobStatus = Find<TextBlock>("AiJobStatus"); aiCompileCandidateButton = Find<Button>("AiCompileCandidateButton"); editorRecipeButton = Find<Button>("EditorRecipeButton"); creatorThemeCount = Find<TextBlock>("CreatorThemeCount");
            seriesStrip = Find<StackPanel>("SeriesStrip"); newSeriesButton = Find<Button>("NewSeriesButton"); renameSeriesButton = Find<Button>("RenameSeriesButton"); deleteSeriesButton = Find<Button>("DeleteSeriesButton");
            allFilter = Find<Button>("AllFilter"); darkFilter = Find<Button>("DarkFilter"); lightFilter = Find<Button>("LightFilter");
            heroContent = Find<Grid>("HeroContent"); heroImage = Find<Image>("HeroImage"); heroName = Find<TextBlock>("HeroName");
            heroMeta = Find<TextBlock>("HeroMeta"); heroDescription = Find<TextBlock>("HeroDescription"); heroApplyButton = Find<Button>("HeroApplyButton"); heroPreviewButton = Find<Button>("HeroPreviewButton");
            heroBackgroundButton = Find<Button>("HeroBackgroundButton"); heroDeleteButton = Find<Button>("HeroDeleteButton");
            heroMoveButton = Find<Button>("HeroMoveButton");
            themeCountLabel = Find<TextBlock>("ThemeCountLabel"); themeScroll = Find<ScrollViewer>("ThemeScroll"); themeStrip = Find<WrapPanel>("ThemeStrip");
            scrollLeftButton = Find<Button>("ScrollLeftButton"); scrollRightButton = Find<Button>("ScrollRightButton");
            activityDock = Find<Border>("ActivityDock"); busyBar = Find<ProgressBar>("BusyBar"); operationTitle = Find<TextBlock>("OperationTitle"); progressText = Find<TextBlock>("ProgressText"); cancelOperationButton = Find<Button>("CancelOperationButton");
            runtimeDot = Find<Ellipse>("RuntimeDot"); runtimeLabel = Find<TextBlock>("RuntimeLabel"); currentThemeValue = Find<TextBlock>("CurrentThemeValue"); runtimeModeValue = Find<TextBlock>("RuntimeModeValue"); runtimeDetailValue = Find<TextBlock>("RuntimeDetailValue");
            pauseButton = Find<Button>("PauseButton"); resumeButton = Find<Button>("ResumeButton"); runtimeVerifyButton = Find<Button>("RuntimeVerifyButton"); rollbackButton = Find<Button>("RollbackButton"); restoreButton = Find<Button>("RestoreButton");
            themeStorePath = Find<TextBlock>("ThemeStorePath"); enginePath = Find<TextBlock>("EnginePath");
            updateStatus = Find<TextBlock>("UpdateStatus"); checkUpdateButton = Find<Button>("CheckUpdateButton");
        }

        private void NormalizePageHeaders()
        {
            // Gold communicates a selected state or a primary action. Page titles are
            // navigation context, so keeping them neutral prevents visual competition.
            foreach (Grid page in new[] { themesPage, aiPage, editorPage, creatorPage, runtimePage, settingsPage })
            {
                TextBlock title = FindFirstTextBlock(page);
                if (title == null) continue;
                title.Foreground = Brush("#ECE8E1");
                title.FontSize = 30;
            }
        }

        private static TextBlock FindFirstTextBlock(DependencyObject root)
        {
            if (root == null) return null;
            for (int index = 0; index < VisualTreeHelper.GetChildrenCount(root); index++)
            {
                DependencyObject child = VisualTreeHelper.GetChild(root, index);
                TextBlock text = child as TextBlock;
                if (text != null) return text;
                text = FindFirstTextBlock(child);
                if (text != null) return text;
            }
            return null;
        }

        private void ConfigureWindow()
        {
            string iconPath = Path.Combine(engineRoot, "assets", "studio.ico");
            if (File.Exists(iconPath))
            {
                BitmapFrame icon = BitmapFrame.Create(new Uri(iconPath), BitmapCreateOptions.PreservePixelFormat, BitmapCacheOption.OnLoad);
                icon.Freeze(); window.Icon = icon; titleIcon.Source = icon;
            }
            titleBar.MouseLeftButtonDown += delegate(object sender, MouseButtonEventArgs e)
            {
                if (e.ClickCount == 2) ToggleMaximize(); else window.DragMove();
            };
            minimizeButton.Click += delegate { window.WindowState = WindowState.Minimized; };
            maximizeButton.Click += delegate { ToggleMaximize(); };
            closeButton.Click += delegate { window.Close(); };
            window.Closing += delegate(object sender, System.ComponentModel.CancelEventArgs e)
            {
                if (!exitRequested)
                {
                    e.Cancel = true;
                    window.Hide();
                }
            };
            window.StateChanged += delegate { maximizeButton.Content = window.WindowState == WindowState.Maximized ? "\uE923" : "\uE922"; };
            heroContent.SizeChanged += delegate { ApplyRoundedClip(heroContent, 15); };

            themesNav.Click += delegate { ShowPage("themes"); };
            aiNav.Click += delegate { ShowPage("ai"); };
            editorNav.Click += delegate { ShowPage("editor"); };
            creatorNav.Click += delegate { ShowPage("creator"); };
            runtimeNav.Click += delegate { ShowPage("runtime"); };
            settingsNav.Click += delegate { ShowPage("settings"); };
            searchBox.TextChanged += delegate
            {
                searchHint.Visibility = string.IsNullOrWhiteSpace(searchBox.Text) ? Visibility.Visible : Visibility.Collapsed;
                themePageStart = 0;
                RefreshCards();
            };
            allFilter.Click += delegate { filter = "all"; themePageStart = 0; RefreshCards(); };
            darkFilter.Click += delegate { filter = "dark"; themePageStart = 0; RefreshCards(); };
            lightFilter.Click += delegate { filter = "light"; themePageStart = 0; RefreshCards(); };
            scrollLeftButton.Click += delegate
            {
                themePageStart = Math.Max(0, themePageStart - ThemePageSize);
                RefreshCards();
            };
            scrollRightButton.Click += delegate
            {
                themePageStart += ThemePageSize;
                RefreshCards();
            };
            heroApplyButton.Click += delegate { if (selectedTheme != null) RunAction("正在应用 " + selectedTheme.Name, "activate", selectedTheme.Id, "-RestartExisting"); };
            heroPreviewButton.Click += delegate { ShowPreview(); };
            heroBackgroundButton.Click += delegate { ChooseLocalBackground(); };
            heroDeleteButton.Click += delegate { DeleteSelectedTheme(); };
            heroMoveButton.Click += delegate { MoveSelectedTheme(); };
            createThemeButton.Click += delegate { OpenThemeGenerator(); };
            importThemeButton.Click += delegate { ImportThemeBundle(null); };
            recipeThemeButton.Click += delegate { CompileRecipeTheme(); };
            aiStartButton.Click += delegate { CreateAiThemeJob(); };
            aiCompileCandidateButton.Click += delegate { CompileAiCandidate(); };
            editorRecipeButton.Click += delegate { CompileRecipeTheme(); };
            newSeriesButton.Click += delegate { CreateSeries(); };
            renameSeriesButton.Click += delegate { RenameSeries(); };
            deleteSeriesButton.Click += delegate { DeleteSeries(); };
            cancelOperationButton.Click += delegate { CancelOperation(); };
            pauseButton.Click += delegate { RunAction("正在暂停主题", "pause"); };
            resumeButton.Click += delegate { RunAction("正在重新应用主题", "resume", "-RestartExisting"); };
            runtimeVerifyButton.Click += delegate { RunAction("正在验证运行时", "verify"); };
            rollbackButton.Click += delegate { RunAction("正在回退主题", "rollback"); };
            restoreButton.Click += delegate { RunAction("正在恢复官方外观", "restore"); };
            checkUpdateButton.Click += delegate { CheckForUpdates(true); };
        }

        private void WindowLoaded(object sender, RoutedEventArgs e)
        {
            ApplyRoundedClip(heroContent, 15);
            LoadThemes();
            RefreshAiJobStatus();
            RefreshSeries();
            RefreshState();
            themeStorePath.Text = Path.Combine(stateRoot, "themes");
            enginePath.Text = engineRoot;
            string updateResult = updateService.ConsumeLastUpdateMessage();
            if (string.IsNullOrWhiteSpace(updateResult)) CheckForUpdates(false); else updateStatus.Text = updateResult;
        }

        public async void CheckForUpdates(bool interactive)
        {
            if (!checkUpdateButton.IsEnabled) return;
            checkUpdateButton.IsEnabled = false;
            updateStatus.Text = "正在检查 GitHub Releases…";
            try
            {
                UpdateCheckResult update = await updateService.CheckAsync();
                updateStatus.Text = update.Message;
                if (!update.Enabled)
                {
                    if (interactive) System.Windows.MessageBox.Show(update.Message, "Codex Theme Studio", MessageBoxButton.OK, MessageBoxImage.Information);
                    return;
                }
                if (!update.UpdateAvailable)
                {
                    if (interactive) System.Windows.MessageBox.Show(update.Message, "Codex Theme Studio", MessageBoxButton.OK, MessageBoxImage.Information);
                    return;
                }
                MessageBoxResult choice = System.Windows.MessageBox.Show(
                    "发现 Codex Theme Studio " + update.Version + "。是否从 GitHub Releases 下载、验证 MSI 更新签名并安装？",
                    "软件更新",
                    MessageBoxButton.YesNo,
                    MessageBoxImage.Information);
                if (choice != MessageBoxResult.Yes) return;
                updateStatus.Text = "正在下载并验证 " + update.Version + "…";
                string installer = await updateService.DownloadAndVerifyAsync(update);
                updateStatus.Text = "验证通过，正在启动升级安装…";
                updateService.StartInstaller(installer, update);
                RequestExit();
            }
            catch (Exception ex)
            {
                updateStatus.Text = "更新失败：" + ex.Message;
                if (interactive) System.Windows.MessageBox.Show(ex.Message, "软件更新", MessageBoxButton.OK, MessageBoxImage.Error);
            }
            finally { checkUpdateButton.IsEnabled = true; }
        }

        private void ToggleMaximize()
        {
            window.WindowState = window.WindowState == WindowState.Maximized ? WindowState.Normal : WindowState.Maximized;
        }

        private static SolidColorBrush Brush(string color)
        {
            SolidColorBrush brush = (SolidColorBrush)new BrushConverter().ConvertFromString(color);
            brush.Freeze();
            return brush;
        }

        private static void ApplyRoundedClip(FrameworkElement element, double radius)
        {
            if (element.ActualWidth <= 0 || element.ActualHeight <= 0) return;
            element.Clip = new RectangleGeometry(new Rect(0, 0, element.ActualWidth, element.ActualHeight), radius, radius);
        }

        private void LoadThemes()
        {
            string selectedId = selectedTheme == null ? string.Empty : selectedTheme.Id;
            themes.Clear();
            string themeRoot = Path.Combine(stateRoot, "themes");
            if (!Directory.Exists(themeRoot)) { selectedTheme = null; return; }
            foreach (string directory in Directory.GetDirectories(themeRoot))
            {
                string themeJson = Path.Combine(directory, "theme.json");
                if (!File.Exists(themeJson)) continue;
                try
                {
                    Dictionary<string, object> data = serializer.DeserializeObject(File.ReadAllText(themeJson, Encoding.UTF8)) as Dictionary<string, object>;
                    if (data == null) continue;
                    ThemeItem item = new ThemeItem();
                    item.Id = Value(data, "id"); item.Name = Value(data, "name"); item.Appearance = Value(data, "appearance");
                    item.SeriesId = engine.Catalog.GetSeriesId(item.Id);
                    item.Directory = directory; item.Layout = "native";
                    Dictionary<string, object> layout = Object(data, "layout");
                    if (layout != null && !string.IsNullOrEmpty(Value(layout, "mode"))) item.Layout = Value(layout, "mode");
                    Dictionary<string, object> assets = Object(data, "assets");
                    string relative = assets == null ? string.Empty : Value(assets, "homeBackground");
                    if (!string.IsNullOrEmpty(relative))
                    {
                        string candidate = Path.GetFullPath(Path.Combine(directory, relative));
                        if (candidate.StartsWith(Path.GetFullPath(directory) + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase) && File.Exists(candidate)) item.BackgroundPath = candidate;
                    }
                    if (string.IsNullOrEmpty(item.BackgroundPath))
                    {
                        string cover = Path.Combine(engineRoot, "assets", "theme-covers", item.Id + ".png");
                        if (File.Exists(cover)) item.BackgroundPath = cover;
                    }
                    if (!string.IsNullOrEmpty(item.Id) && !string.IsNullOrEmpty(item.Name)) themes.Add(item);
                }
                catch { }
            }
            if (creatorThemeCount != null) creatorThemeCount.Text = themes.Count.ToString();
            selectedTheme = themes.FirstOrDefault(delegate(ThemeItem item) { return string.Equals(item.Id, selectedId, StringComparison.Ordinal); });
        }

        private static Dictionary<string, object> Object(Dictionary<string, object> data, string key)
        {
            object value;
            return data.TryGetValue(key, out value) ? value as Dictionary<string, object> : null;
        }

        private static string Value(Dictionary<string, object> data, string key)
        {
            object value;
            return data.TryGetValue(key, out value) && value != null ? Convert.ToString(value) : string.Empty;
        }

        private BitmapSource LoadBitmap(string path, int decodeWidth)
        {
            if (string.IsNullOrEmpty(path) || !File.Exists(path)) return null;
            DateTime stamp = File.GetLastWriteTimeUtc(path);
            string key = path + "|" + stamp.Ticks + "|" + decodeWidth;
            BitmapSource cached;
            lock (imageCacheSync) if (imageCache.TryGetValue(key, out cached)) return cached;
            BitmapImage bitmap = new BitmapImage();
            bitmap.BeginInit(); bitmap.CacheOption = BitmapCacheOption.OnLoad; bitmap.DecodePixelWidth = decodeWidth; bitmap.UriSource = new Uri(path); bitmap.EndInit(); bitmap.Freeze();
            lock (imageCacheSync)
            {
                if (!imageCache.ContainsKey(key))
                {
                    imageCache[key] = bitmap;
                    imageCacheOrder.Enqueue(key);
                    while (imageCacheOrder.Count > 48) imageCache.Remove(imageCacheOrder.Dequeue());
                }
            }
            return bitmap;
        }

        private void RefreshState()
        {
            string statePath = Path.Combine(stateRoot, "state.json");
            if (File.Exists(statePath))
            {
                try
                {
                    Dictionary<string, object> state = serializer.DeserializeObject(File.ReadAllText(statePath, Encoding.UTF8)) as Dictionary<string, object>;
                    currentThemeId = state == null ? string.Empty : Value(state, "currentThemeId");
                    int pid;
                    if (state != null && int.TryParse(Value(state, "injectorPid"), out pid))
                    {
                        try { Process process = Process.GetProcessById(pid); process.Dispose(); } catch { }
                    }
                }
                catch { currentThemeId = string.Empty; }
            }
            string runtimeStatus = engine.GetRuntimeStatus(false);
            ThemeItem current = themes.FirstOrDefault(delegate(ThemeItem item) { return string.Equals(item.Id, currentThemeId, StringComparison.Ordinal); });
            currentThemeValue.Text = current == null ? "官方外观" : current.Name;
            UpdateRuntimeStatus(runtimeStatus);
            if (selectedTheme == null) selectedTheme = current ?? themes.FirstOrDefault();
            RefreshCards();
            SetHero(selectedTheme);
        }

        private void SupervisorHealthChanged(object sender, RuntimeHealthChangedEventArgs e)
        {
            if (window == null || window.Dispatcher.HasShutdownStarted) return;
            window.Dispatcher.BeginInvoke(new Action(delegate { UpdateRuntimeStatus(e.Status); }), DispatcherPriority.Background);
        }

        private void UpdateRuntimeStatus(string status)
        {
            string label;
            string mode;
            string detail;
            string color;
            switch (status)
            {
                case "HEALTHY":
                    label = "运行时正常"; mode = "主题运行中"; color = "#50C989";
                    detail = "watcher、Codex 与 CDP 身份一致，主题增量同步正常。";
                    break;
                case "SELF_HEALING":
                    label = "正在自愈"; mode = "正在重连渲染器"; color = "#69A7FF";
                    detail = "CDP 连接仍有效，RuntimeSupervisor 正在安全重启 watcher。";
                    break;
                case "NEEDS_RESTART":
                    label = "需要重启"; mode = "等待用户确认"; color = "#D8A757";
                    detail = "Codex 正在运行但 CDP 身份不可恢复。Studio 不会静默结束 Codex，请点击“重新应用”并确认。";
                    break;
                case "PAUSED":
                    label = "主题已暂停"; mode = "官方外观"; color = "#8E939B";
                    detail = "主题数据和回退点均已保留，点击“重新应用”可恢复。";
                    break;
                case "OFFLINE":
                    label = "Codex 未连接"; mode = "等待启动"; color = "#D8A757";
                    detail = "当前没有可用的 Codex CDP 会话；点击“重新应用”会以普通方式启动 Codex。";
                    break;
                default:
                    label = "运行时故障"; mode = "需要检查"; color = "#E56B73";
                    detail = "运行监督检测到异常。可先运行验证，或暂停后重新应用。";
                    break;
            }
            runtimeLabel.Text = label;
            runtimeDot.Fill = Brush(color);
            runtimeModeValue.Text = mode;
            runtimeDetailValue.Text = detail;
        }

        private void RefreshSeries()
        {
            if (seriesStrip == null) return;
            seriesStrip.Children.Clear();
            IList<ThemeSeries> items = engine.Catalog.GetSeries();
            if (!items.Any(item => item.Id == selectedSeriesId)) selectedSeriesId = ThemeCatalog.AllSeriesId;
            foreach (ThemeSeries item in items)
            {
                Button button = new Button {
                    Content = item.Name,
                    Style = (Style)window.FindResource("FilterButton"),
                    Margin = new Thickness(0, 0, 7, 0),
                    Tag = item.Id
                };
                SetFilterStyle(button, item.Id == selectedSeriesId);
                button.Click += delegate(object sender, RoutedEventArgs e)
                {
                    selectedSeriesId = Convert.ToString(((Button)sender).Tag);
                    themePageStart = 0;
                    RefreshSeries();
                    RefreshCards();
                };
                seriesStrip.Children.Add(button);
            }
            bool editable = selectedSeriesId != ThemeCatalog.AllSeriesId && selectedSeriesId != ThemeCatalog.UnclassifiedSeriesId;
            renameSeriesButton.IsEnabled = editable;
            deleteSeriesButton.IsEnabled = editable;
        }

        private void CreateSeries()
        {
            string name = ShowTextPrompt("新建系列", "系列名称（支持中文）", string.Empty);
            if (string.IsNullOrWhiteSpace(name)) return;
            try
            {
                selectedSeriesId = engine.Catalog.CreateSeries(name);
                themePageStart = 0;
                RefreshSeries();
                RefreshCards();
            }
            catch (Exception ex) { System.Windows.MessageBox.Show(ex.Message, "系列管理", MessageBoxButton.OK, MessageBoxImage.Error); }
        }

        private void RenameSeries()
        {
            ThemeSeries item = engine.Catalog.GetSeries().FirstOrDefault(value => value.Id == selectedSeriesId);
            if (item == null || item.Id == ThemeCatalog.AllSeriesId || item.Id == ThemeCatalog.UnclassifiedSeriesId) return;
            string name = ShowTextPrompt("重命名系列", "新的系列名称", item.Name);
            if (string.IsNullOrWhiteSpace(name)) return;
            try { engine.Catalog.RenameSeries(item.Id, name); RefreshSeries(); }
            catch (Exception ex) { System.Windows.MessageBox.Show(ex.Message, "系列管理", MessageBoxButton.OK, MessageBoxImage.Error); }
        }

        private void DeleteSeries()
        {
            ThemeSeries item = engine.Catalog.GetSeries().FirstOrDefault(value => value.Id == selectedSeriesId);
            if (item == null || item.Id == ThemeCatalog.AllSeriesId || item.Id == ThemeCatalog.UnclassifiedSeriesId) return;
            if (System.Windows.MessageBox.Show(
                "删除系列“" + item.Name + "”？系列内主题将移至“未分类”，主题文件不会删除。",
                "删除系列",
                MessageBoxButton.YesNo,
                MessageBoxImage.Warning) != MessageBoxResult.Yes) return;
            engine.Catalog.DeleteSeries(item.Id);
            foreach (ThemeItem theme in themes) theme.SeriesId = engine.Catalog.GetSeriesId(theme.Id);
            selectedSeriesId = ThemeCatalog.UnclassifiedSeriesId;
            themePageStart = 0;
            RefreshSeries();
            RefreshCards();
        }

        private void MoveSelectedTheme()
        {
            if (selectedTheme == null) return;
            ThemeSeries target = ShowSeriesPrompt(engine.Catalog.GetSeries().Where(
                item => item.Id != ThemeCatalog.AllSeriesId).ToList());
            if (target == null) return;
            engine.Catalog.MoveTheme(selectedTheme.Id, target.Id);
            selectedTheme.SeriesId = engine.Catalog.GetSeriesId(selectedTheme.Id);
            selectedSeriesId = selectedTheme.SeriesId;
            themePageStart = 0;
            RefreshSeries();
            RefreshCards();
        }

        private string ShowTextPrompt(string title, string label, string initialValue)
        {
            Window dialog = new Window {
                Title = title, Width = 460, Height = 220, Owner = window,
                WindowStartupLocation = WindowStartupLocation.CenterOwner,
                ResizeMode = ResizeMode.NoResize, Background = Brush("#111318"), Foreground = Brush("#EEE4D7"),
                FontFamily = new FontFamily("Microsoft YaHei UI")
            };
            StackPanel stack = new StackPanel { Margin = new Thickness(24) };
            stack.Children.Add(new TextBlock { Text = label, Foreground = Brush("#C9B89F"), Margin = new Thickness(0, 0, 0, 10) });
            TextBox input = new TextBox { Text = initialValue ?? string.Empty, Height = 38, Padding = new Thickness(10, 7, 10, 7), Background = Brush("#1A1C21"), Foreground = Brush("#F5E8D4"), BorderBrush = Brush("#4B4640") };
            stack.Children.Add(input);
            StackPanel actions = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Right, Margin = new Thickness(0, 20, 0, 0) };
            Button cancel = new Button { Content = "取消", Width = 86, Style = (Style)window.FindResource("ActionButton"), Margin = new Thickness(0, 0, 8, 0) };
            Button confirm = new Button { Content = "确认", Width = 86, Style = (Style)window.FindResource("PrimaryButton") };
            actions.Children.Add(cancel); actions.Children.Add(confirm); stack.Children.Add(actions); dialog.Content = stack;
            cancel.Click += delegate { dialog.DialogResult = false; };
            confirm.Click += delegate { dialog.DialogResult = true; };
            dialog.Loaded += delegate { input.Focus(); input.SelectAll(); };
            return dialog.ShowDialog() == true ? input.Text.Trim() : null;
        }

        private ThemeSeries ShowSeriesPrompt(IList<ThemeSeries> items)
        {
            Window dialog = new Window {
                Title = "移动到系列", Width = 440, Height = 210, Owner = window,
                WindowStartupLocation = WindowStartupLocation.CenterOwner, ResizeMode = ResizeMode.NoResize,
                Background = Brush("#111318"), Foreground = Brush("#EEE4D7")
            };
            StackPanel stack = new StackPanel { Margin = new Thickness(24) };
            stack.Children.Add(new TextBlock { Text = "选择目标系列", Foreground = Brush("#C9B89F"), Margin = new Thickness(0, 0, 0, 10) });
            ComboBox combo = new ComboBox { ItemsSource = items, DisplayMemberPath = "Name", SelectedIndex = 0, Height = 38 };
            stack.Children.Add(combo);
            Button confirm = new Button { Content = "移动", Width = 96, HorizontalAlignment = HorizontalAlignment.Right, Margin = new Thickness(0, 20, 0, 0), Style = (Style)window.FindResource("PrimaryButton") };
            confirm.Click += delegate { dialog.DialogResult = true; };
            stack.Children.Add(confirm); dialog.Content = stack;
            return dialog.ShowDialog() == true ? combo.SelectedItem as ThemeSeries : null;
        }

        private void RefreshCards()
        {
            if (themeStrip == null) return;
            string query = (searchBox.Text ?? string.Empty).Trim();
            List<ThemeItem> visible = themes.Where(delegate(ThemeItem item)
            {
                bool filterMatch = filter == "all" || string.Equals(item.Appearance, filter, StringComparison.OrdinalIgnoreCase);
                bool queryMatch = query.Length == 0 || (item.Name + " " + item.Id).IndexOf(query, StringComparison.OrdinalIgnoreCase) >= 0;
                bool seriesMatch = selectedSeriesId == ThemeCatalog.AllSeriesId ||
                    string.Equals(item.SeriesId, selectedSeriesId, StringComparison.Ordinal);
                return filterMatch && queryMatch && seriesMatch;
            }).OrderBy(item => engine.Catalog.GetThemeOrder(item.Id)).ThenBy(item => item.Name).ToList();
            int lastPageStart = visible.Count == 0 ? 0 : ((visible.Count - 1) / ThemePageSize) * ThemePageSize;
            themePageStart = Math.Max(0, Math.Min(themePageStart, lastPageStart));
            List<ThemeItem> page = visible.Skip(themePageStart).Take(ThemePageSize).ToList();
            if (selectedTheme == null || !visible.Any(delegate(ThemeItem item) { return item.Id == selectedTheme.Id; })) selectedTheme = visible.FirstOrDefault();
            themeStrip.Children.Clear();
            foreach (ThemeItem item in page) themeStrip.Children.Add(CreateCard(item));
            int pageEnd = Math.Min(themePageStart + page.Count, visible.Count);
            themeCountLabel.Text = visible.Count == 0
                ? "· 0 / " + themes.Count
                : "· " + (themePageStart + 1) + "–" + pageEnd + " / " + visible.Count + "（总计 " + themes.Count + "）";
            scrollLeftButton.IsEnabled = themePageStart > 0;
            scrollRightButton.IsEnabled = themePageStart + ThemePageSize < visible.Count;
            SetFilterStyle(allFilter, filter == "all"); SetFilterStyle(darkFilter, filter == "dark"); SetFilterStyle(lightFilter, filter == "light");
            themeScroll.ScrollToHorizontalOffset(0);
            SetHero(selectedTheme);
        }

        private static void SetFilterStyle(Button button, bool selected)
        {
            button.Background = Brush(selected ? "#2B241C" : "#17191D");
            button.BorderBrush = Brush(selected ? "#D6AE78" : "#3A3733");
            button.Foreground = Brush(selected ? "#F1D5AE" : "#EEE4D7");
        }

        private Border CreateCard(ThemeItem item)
        {
            Border card = new Border(); card.Width = 286; card.Height = 292; card.Margin = new Thickness(0, 0, 18, 18); card.CornerRadius = new CornerRadius(14); card.Cursor = Cursors.Hand;
            card.Background = Brush("#111318"); card.BorderThickness = new Thickness(selectedTheme != null && selectedTheme.Id == item.Id ? 2 : 1);
            card.BorderBrush = Brush(selectedTheme != null && selectedTheme.Id == item.Id ? "#D6AE78" : "#34312E");
            Grid layout = new Grid(); layout.RowDefinitions.Add(new RowDefinition { Height = new GridLength(164) }); layout.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
            layout.SizeChanged += delegate { ApplyRoundedClip(layout, 10); };
            Grid visual = new Grid(); Image image = new Image(); image.Stretch = Stretch.UniformToFill; visual.Children.Add(image);
            card.Loaded += async delegate
            {
                string source = await Task.Run(delegate { return assetCache.GetThumbnail(item.BackgroundPath); });
                BitmapSource thumbnail = await Task.Run(delegate { return LoadBitmap(source, 480); });
                if (card.IsLoaded) image.Source = thumbnail;
            };
            if (item.Id == currentThemeId)
            {
                Border badge = new Border { Background = Brush("#E7C18D"), CornerRadius = new CornerRadius(8), Padding = new Thickness(8, 3, 8, 3), HorizontalAlignment = HorizontalAlignment.Right, VerticalAlignment = VerticalAlignment.Top, Margin = new Thickness(8) };
                badge.Child = new TextBlock { Text = "当前", Foreground = Brush("#1A120A"), FontSize = 10, FontWeight = FontWeights.SemiBold }; visual.Children.Add(badge);
            }
            Grid.SetRow(visual, 0); layout.Children.Add(visual);
            StackPanel detail = new StackPanel { Margin = new Thickness(14, 11, 14, 13) };
            detail.Children.Add(new TextBlock { Text = item.Name, FontSize = 15, FontWeight = FontWeights.SemiBold, Foreground = Brush("#F0E1CE"), TextTrimming = TextTrimming.CharacterEllipsis });
            detail.Children.Add(new TextBlock { Text = (item.Layout == "native" ? "原生布局" : item.Layout) + " · " + (item.Appearance == "light" ? "浅色" : "深色"), FontSize = 11, Foreground = Brush("#9F9B94"), Margin = new Thickness(0, 5, 0, 8) });
            Button apply = new Button { Content = item.Id == currentThemeId ? "正在使用" : "▷  应用主题", Style = (Style)window.FindResource(item.Id == currentThemeId ? "ActionButton" : "PrimaryButton"), Height = 34, IsEnabled = item.Id != currentThemeId && operationCancellation == null };
            apply.Click += delegate(object sender, RoutedEventArgs e) { selectedTheme = item; e.Handled = true; RunAction("正在应用 " + item.Name, "activate", item.Id, "-RestartExisting"); };
            detail.Children.Add(apply); Grid.SetRow(detail, 1); layout.Children.Add(detail); card.Child = layout;
            card.MouseLeftButtonUp += delegate { selectedTheme = item; SetHero(item); RefreshCards(); };
            return card;
        }

        private void SetHero(ThemeItem item)
        {
            if (item == null) return;
            selectedTheme = item; heroImage.Source = LoadBitmap(item.BackgroundPath, 1400); heroName.Text = item.Name;
            heroMeta.Text = (item.Appearance == "light" ? "浅色" : "深色") + " · " + (item.Layout == "native" ? "原生布局" : item.Layout + " 布局") + " · 已验证";
            heroDescription.Text = item.Appearance == "light" ? "轻盈通透的视觉氛围，为阅读、整理与白天创作提供清晰舒适的工作空间。" : "深邃克制的暗色氛围，为长时间创作提供专注、舒适且沉浸的视觉体验。";
            bool current = item.Id == currentThemeId;
            heroApplyButton.Content = current ? "正在使用" : "应用主题";
            heroApplyButton.IsEnabled = !current && operationCancellation == null;
            heroBackgroundButton.IsEnabled = operationCancellation == null;
            heroDeleteButton.IsEnabled = !current && operationCancellation == null;
        }

        private void ShowPage(string page)
        {
            themesPage.Visibility = page == "themes" ? Visibility.Visible : Visibility.Collapsed;
            aiPage.Visibility = page == "ai" ? Visibility.Visible : Visibility.Collapsed;
            editorPage.Visibility = page == "editor" ? Visibility.Visible : Visibility.Collapsed;
            creatorPage.Visibility = page == "creator" ? Visibility.Visible : Visibility.Collapsed;
            runtimePage.Visibility = page == "runtime" ? Visibility.Visible : Visibility.Collapsed;
            settingsPage.Visibility = page == "settings" ? Visibility.Visible : Visibility.Collapsed;
            SetNavStyle(themesNav, page == "themes"); SetNavStyle(aiNav, page == "ai"); SetNavStyle(editorNav, page == "editor"); SetNavStyle(creatorNav, page == "creator"); SetNavStyle(runtimeNav, page == "runtime"); SetNavStyle(settingsNav, page == "settings");
        }

        private static void SetNavStyle(Button button, bool active)
        {
            button.Background = Brush(active ? "#19191B" : "Transparent"); button.BorderBrush = Brush(active ? "#D6AE78" : "Transparent"); button.Foreground = Brush(active ? "#F0D4AB" : "#BDB5AB");
        }

        private void SetBusy(bool busy, string label)
        {
            activityDock.Visibility = busy ? Visibility.Visible : Visibility.Collapsed; operationTitle.Text = label;
            foreach (Button button in new[] { importThemeButton, recipeThemeButton, createThemeButton, aiStartButton, editorRecipeButton, heroApplyButton, heroBackgroundButton, heroMoveButton, heroDeleteButton, newSeriesButton, renameSeriesButton, deleteSeriesButton, pauseButton, resumeButton, runtimeVerifyButton, rollbackButton, restoreButton }) button.IsEnabled = !busy;
            if (busy) { busyBar.Value = 4; progressText.Text = " · 4%"; cancelOperationButton.IsEnabled = true; }
            else
            {
                try { RefreshSeries(); RefreshCards(); }
                catch (Exception ex) { RecordClientFailure("busy-reset", string.Empty, null, ex); }
            }
        }

        private void UpdateProgress(object sender, EventArgs e)
        {
            double elapsed = (DateTime.UtcNow - operationStartedAt).TotalSeconds;
            double value = Math.Min(92, Math.Round(4 + elapsed * 10)); busyBar.Value = value; progressText.Text = " · " + value + "%";
        }

        private async void RunAction(string label, params string[] arguments)
        {
            if (operationCancellation != null) return;
            if (arguments != null && arguments.Length > 0 &&
                (string.Equals(arguments[0], "activate", StringComparison.OrdinalIgnoreCase) ||
                 string.Equals(arguments[0], "resume", StringComparison.OrdinalIgnoreCase) ||
                 string.Equals(arguments[0], "rollback", StringComparison.OrdinalIgnoreCase) ||
                 (string.Equals(arguments[0], "set-background", StringComparison.OrdinalIgnoreCase) && arguments.Length > 1 && string.Equals(arguments[1], currentThemeId, StringComparison.Ordinal))) &&
                engine.RequiresCodexRestart())
            {
                MessageBoxResult restart = System.Windows.MessageBox.Show(
                    "Codex 需要重启一次以建立安全的本机主题连接。未保存的输入可能丢失，是否继续？",
                    "Codex Theme Studio",
                    MessageBoxButton.OKCancel,
                    MessageBoxImage.Warning);
                if (restart != MessageBoxResult.OK) return;
                if (!arguments.Any(value => string.Equals(value, "-RestartExisting", StringComparison.OrdinalIgnoreCase)))
                    arguments = arguments.Concat(new[] { "-RestartExisting" }).ToArray();
            }
            operationCancellation = new CancellationTokenSource(); operationStartedAt = DateTime.UtcNow; SetBusy(true, label); progressTimer.Start();
            try
            {
                EngineCommandResult result = await ExecuteEngineAsync(arguments, operationCancellation.Token, TimeSpan.FromSeconds(120));
                if (result.ExitCode != 0)
                {
                    string detail = (result.StandardError + Environment.NewLine + result.StandardOutput).Trim();
                    throw new InvalidOperationException(detail.Length == 0 ? label + "失败，退出代码 " + result.ExitCode + "。" : detail);
                }
                busyBar.Value = 100; progressText.Text = " · 100%";
                string command = arguments != null && arguments.Length > 0 ? arguments[0] : string.Empty;
                if (command == "set-background" || command == "delete" || command == "create-recipe") LoadThemes();
                try { RefreshState(); }
                catch (Exception ex)
                {
                    RecordClientFailure("post-success-refresh", label, arguments, ex);
                    string completed = string.Equals(command, "activate", StringComparison.OrdinalIgnoreCase)
                        ? "主题已经切换成功，但 Studio 刷新界面时遇到问题。重新打开 Studio 即可同步当前状态。"
                        : label + "已完成，但 Studio 刷新界面时遇到问题。重新打开 Studio 即可同步当前状态。";
                    System.Windows.MessageBox.Show(completed + Environment.NewLine + Environment.NewLine + ex.Message, "Codex Theme Studio", MessageBoxButton.OK, MessageBoxImage.Warning);
                }
                if (command == "set-background") System.Windows.MessageBox.Show("本地背景已保存，并同时用于首页与任务页。", "Codex Theme Studio", MessageBoxButton.OK, MessageBoxImage.Information);
                if (command == "delete") System.Windows.MessageBox.Show("主题已从主题库删除，并保留了本地可恢复备份。", "Codex Theme Studio", MessageBoxButton.OK, MessageBoxImage.Information);
                if (command == "create-recipe") System.Windows.MessageBox.Show("配方已编译到“AI 配方”系列。请先预览，再单独确认应用主题。", "Codex Theme Studio", MessageBoxButton.OK, MessageBoxImage.Information);
            }
            catch (OperationCanceledException) { }
            catch (TimeoutException ex)
            {
                RecordClientFailure("operation-timeout", label, arguments, ex);
                System.Windows.MessageBox.Show(ex.Message, "Codex Theme Studio", MessageBoxButton.OK, MessageBoxImage.Warning);
            }
            catch (Exception ex)
            {
                RecordClientFailure("operation-failed", label, arguments, ex);
                System.Windows.MessageBox.Show(ex.Message, "Codex Theme Studio", MessageBoxButton.OK, MessageBoxImage.Error);
            }
            finally
            {
                progressTimer.Stop();
                if (operationCancellation != null) { operationCancellation.Dispose(); operationCancellation = null; }
                SetBusy(false, string.Empty);
            }
        }

        private void RecordClientFailure(string phase, string label, string[] arguments, Exception error)
        {
            try
            {
                string logDirectory = Path.Combine(stateRoot, "logs");
                Directory.CreateDirectory(logDirectory);
                string command = arguments != null && arguments.Length > 0 ? arguments[0] : string.Empty;
                string message = (error == null ? string.Empty : error.ToString()).Replace("\r", " ").Replace("\n", " ");
                string entry = DateTimeOffset.Now.ToString("o") + "\t" + phase + "\t" + command + "\t" + label + "\t" + message + Environment.NewLine;
                File.AppendAllText(Path.Combine(logDirectory, "studio-client.log"), entry, new UTF8Encoding(false));
            }
            catch
            {
                // NOTE: Diagnostic logging must never turn a recoverable UI refresh problem into an operation failure.
            }
        }

        private async Task<EngineCommandResult> ExecuteEngineAsync(string[] arguments, CancellationToken cancellationToken, TimeSpan timeout)
        {
            return await engine.ExecuteAsync(arguments, cancellationToken, timeout);
        }

        private void CancelOperation()
        {
            cancelOperationButton.IsEnabled = false; operationTitle.Text = "正在取消操作";
            if (operationCancellation != null) operationCancellation.Cancel();
            engine.CancelActiveOperation();
        }

        private void ShowPreview()
        {
            if (selectedTheme == null) return;
            Window preview = new Window { Title = selectedTheme.Name + " · 预览", Width = 1040, Height = 660, Owner = window, WindowStartupLocation = WindowStartupLocation.CenterOwner, Background = Brush("#0A0C10"), Icon = window.Icon };
            Grid grid = new Grid(); Image image = new Image { Source = LoadBitmap(selectedTheme.BackgroundPath, 1400), Stretch = Stretch.UniformToFill }; grid.Children.Add(image);
            Border panel = new Border { Width = 420, HorizontalAlignment = HorizontalAlignment.Left, Margin = new Thickness(38), Padding = new Thickness(28), CornerRadius = new CornerRadius(16), Background = Brush("#E6121418") };
            StackPanel stack = new StackPanel(); stack.Children.Add(new TextBlock { Text = selectedTheme.Name, FontSize = 30, Foreground = Brush("#F4DFC1"), Margin = new Thickness(0, 0, 0, 14) }); stack.Children.Add(new TextBlock { Text = selectedTheme.Id, FontSize = 12, Foreground = Brush("#B8B0A6") }); panel.Child = stack; grid.Children.Add(panel); preview.Content = grid; preview.ShowDialog();
        }

        public async void ImportThemeBundle(string packagePath)
        {
            if (operationCancellation != null) return;
            if (string.IsNullOrWhiteSpace(packagePath))
            {
                Microsoft.Win32.OpenFileDialog dialog = new Microsoft.Win32.OpenFileDialog {
                    Title = "导入 Codex 主题 Bundle",
                    Filter = "Codex Theme Bundle (*.codextheme)|*.codextheme",
                    CheckFileExists = true,
                    Multiselect = false
                };
                if (dialog.ShowDialog(window) != true) return;
                packagePath = dialog.FileName;
            }
            operationCancellation = new CancellationTokenSource();
            try
            {
                EngineCommandResult previewResult = await engine.ExecuteAsync(
                    new[] { "preview", packagePath },
                    operationCancellation.Token,
                    TimeSpan.FromSeconds(45));
                if (previewResult.ExitCode != 0) throw new InvalidDataException(previewResult.StandardError);
                Dictionary<string, object> preview = serializer.DeserializeObject(previewResult.StandardOutput) as Dictionary<string, object>;
                if (preview == null) throw new InvalidDataException("Bundle 预览结果无效。");
                object[] ids = preview["themeIds"] as object[];
                object[] conflicts = preview["conflicts"] as object[];
                Dictionary<string, object> series = preview["series"] as Dictionary<string, object>;
                string summary = "系列：" + Value(series, "name") + Environment.NewLine +
                    "主题数：" + (ids == null ? 0 : ids.Length) + Environment.NewLine +
                    "校验：Bundle v1、SHA-256 与 Theme Pack v2 已通过";
                if (conflicts != null && conflicts.Length > 0)
                {
                    summary += Environment.NewLine + "冲突：" + string.Join(", ", conflicts.Select(Convert.ToString));
                    System.Windows.MessageBox.Show(summary + Environment.NewLine + "整包未导入，也不会覆盖现有主题。", "导入预览", MessageBoxButton.OK, MessageBoxImage.Warning);
                    return;
                }
                if (System.Windows.MessageBox.Show(
                    summary + Environment.NewLine + Environment.NewLine + "确认导入？导入后不会自动激活。",
                    "导入主题",
                    MessageBoxButton.YesNo,
                    MessageBoxImage.Information) != MessageBoxResult.Yes) return;

                SetBusy(true, "正在安全导入主题 Bundle");
                EngineCommandResult imported = await engine.ExecuteAsync(
                    new[] { "import", packagePath },
                    operationCancellation.Token,
                    TimeSpan.FromSeconds(120));
                if (imported.ExitCode != 0) throw new InvalidDataException(imported.StandardError);
                LoadThemes();
                RefreshSeries();
                RefreshState();
                System.Windows.MessageBox.Show("主题 Bundle 已完整导入，尚未激活。", "导入完成", MessageBoxButton.OK, MessageBoxImage.Information);
            }
            catch (OperationCanceledException) { }
            catch (Exception ex) { System.Windows.MessageBox.Show(ex.Message, "导入主题", MessageBoxButton.OK, MessageBoxImage.Error); }
            finally
            {
                if (operationCancellation != null) { operationCancellation.Dispose(); operationCancellation = null; }
                SetBusy(false, string.Empty);
            }
        }

        private void ChooseLocalBackground()
        {
            if (selectedTheme == null) return;
            Microsoft.Win32.OpenFileDialog dialog = new Microsoft.Win32.OpenFileDialog
            {
                Title = "选择本地主题背景",
                Filter = "PNG 或 JPEG 图片|*.png;*.jpg;*.jpeg",
                CheckFileExists = true,
                Multiselect = false
            };
            if (dialog.ShowDialog(window) != true) return;
            RunAction("正在更新 " + selectedTheme.Name + " 的背景", "set-background", selectedTheme.Id, dialog.FileName);
        }

        private void DeleteSelectedTheme()
        {
            if (selectedTheme == null) return;
            if (string.Equals(selectedTheme.Id, currentThemeId, StringComparison.Ordinal))
            {
                System.Windows.MessageBox.Show("当前正在使用的主题不能删除，请先切换到其他主题。", "Codex Theme Studio", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }
            MessageBoxResult choice = System.Windows.MessageBox.Show(
                "确定删除主题“" + selectedTheme.Name + "”吗？\n\n主题会从列表移除，并保留一份本地可恢复备份。",
                "删除主题",
                MessageBoxButton.YesNo,
                MessageBoxImage.Warning);
            if (choice == MessageBoxResult.Yes) RunAction("正在删除 " + selectedTheme.Name, "delete", selectedTheme.Id);
        }

        private void OpenThemeGenerator()
        {
            try
            {
                string promptPath = Path.Combine(engineRoot, "assets", "create-theme-prompt.txt");
                string prompt = File.ReadAllText(promptPath, Encoding.UTF8).Trim();
                Clipboard.SetText(prompt);
                Process.Start(new ProcessStartInfo("explorer.exe", "shell:AppsFolder\\OpenAI.Codex_2p2nqsd0c76g0!App") { UseShellExecute = true });
                System.Windows.MessageBox.Show("已打开 Codex 并复制主题生成提示词。生成后先导入，再单独确认激活。", "Codex Theme Studio", MessageBoxButton.OK, MessageBoxImage.Information);
            }
            catch (Exception ex) { System.Windows.MessageBox.Show(ex.Message, "Codex Theme Studio", MessageBoxButton.OK, MessageBoxImage.Error); }
        }

        private void CreateAiThemeJob()
        {
            try
            {
                AiThemeJob job = aiJobs.Create(aiPromptBox.Text);
                ThreadPool.QueueUserWorkItem(delegate
                {
                    try
                    {
                        using (CodexAppServerClient server = new CodexAppServerClient())
                        {
                            server.Connect();
                            Dictionary<string, object> started = server.Request("thread/start", new Dictionary<string, object> { { "cwd", aiJobs.JobDirectory(job.Id) }, { "approvalPolicy", "never" }, { "sandbox", "workspace-write" } }, 30000);
                            Dictionary<string, object> thread = started.ContainsKey("thread") ? started["thread"] as Dictionary<string, object> : null;
                            if (thread == null || !thread.ContainsKey("id")) throw new InvalidDataException("Codex app-server 未返回 thread ID。" );
                            string threadId = Convert.ToString(thread["id"]); aiJobs.SetThread(job.Id, threadId);
                            string savedImage = null; string agentText = null; ManualResetEvent completed = new ManualResetEvent(false);
                            server.Notification += delegate(string method, Dictionary<string, object> parameters)
                            {
                                if (method == "item/completed" && parameters.ContainsKey("item"))
                                {
                                    Dictionary<string, object> item = parameters["item"] as Dictionary<string, object>;
                                    if (item != null && string.Equals(Convert.ToString(item.ContainsKey("type") ? item["type"] : ""), "imageGeneration", StringComparison.Ordinal) && item.ContainsKey("savedPath")) savedImage = Convert.ToString(item["savedPath"]);
                                    if (item != null && string.Equals(Convert.ToString(item.ContainsKey("type") ? item["type"] : ""), "agentMessage", StringComparison.Ordinal) && item.ContainsKey("text")) agentText = Convert.ToString(item["text"]);
                                }
                                if (method == "turn/completed") completed.Set();
                            };
                            string imagePrompt = "Mode: generate-image. Generate exactly ONE 1600x900 or larger pure background artwork for Codex Theme Studio. Original request: " + job.Prompt + "\nDo not include text, logos, watermarks, UI, windows, panels, code, terminal, or mockups. Keep calm negative space for the real interface.";
                            server.Request("turn/start", new Dictionary<string, object> { { "threadId", threadId }, { "input", new object[] { new Dictionary<string, object> { { "type", "text" }, { "text", imagePrompt }, { "text_elements", new object[0] } } } } }, 30000);
                            if (!completed.WaitOne(TimeSpan.FromMinutes(4))) throw new TimeoutException("候选图生成超时。" );
                            if (string.IsNullOrWhiteSpace(savedImage)) throw new InvalidDataException("Codex 未返回候选主图。" );
                            string managedImage = aiJobs.AddGeneratedImage(job.Id, savedImage);
                            completed.Reset(); agentText = null;
                            string recipePrompt = "Mode: use-reference-image. Using the provided image, return ONLY a valid Theme Recipe v1 JSON object. Required top-level keys: schemaVersion=1, name, layout, appearance:{density}, paletteIntent:{appearance}. layout must be one of dream-banner, split-studio, full-canvas, terminal-grid, paper-board, minimal-focus, retro-messenger, silk-scroll. No markdown, no commentary. Name and visual choices must reflect: " + job.Prompt;
                            server.Request("turn/start", new Dictionary<string, object> { { "threadId", threadId }, { "input", new object[] { new Dictionary<string, object> { { "type", "text" }, { "text", recipePrompt }, { "text_elements", new object[0] } }, new Dictionary<string, object> { { "type", "localImage" }, { "path", managedImage } } } } }, 30000);
                            if (!completed.WaitOne(TimeSpan.FromMinutes(2))) throw new TimeoutException("主题配方生成超时。" );
                            string recipeJson = ExtractJsonObject(agentText);
                            if (string.IsNullOrWhiteSpace(recipeJson)) throw new InvalidDataException("Codex 未返回有效 Theme Recipe JSON。" );
                            string recipePath = Path.Combine(aiJobs.JobDirectory(job.Id), "generated", "recipe-" + DateTime.UtcNow.ToString("yyyyMMddHHmmss") + ".json");
                            File.WriteAllText(recipePath, recipeJson + Environment.NewLine, new UTF8Encoding(false));
                            aiJobs.AddCandidate(job.Id, recipePath, managedImage);
                        }
                        window.Dispatcher.BeginInvoke(new Action(RefreshAiJobStatus));
                    }
                    catch (Exception ex) { window.Dispatcher.BeginInvoke(new Action(delegate { aiJobStatus.Text = "app-server 连接失败：" + ex.Message; })); }
                });
                RefreshAiJobStatus();
                System.Windows.MessageBox.Show("正在生成主题。完成后点击“一键导入主题库”即可安全写入本地主题库，仍不会自动应用。", "AI 生成主题", MessageBoxButton.OK, MessageBoxImage.Information);
            }
            catch (Exception ex) { System.Windows.MessageBox.Show(ex.Message, "AI 生成主题", MessageBoxButton.OK, MessageBoxImage.Error); }
        }

        private void CompileAiCandidate()
        {
            try
            {
                if (operationCancellation != null) return;
                AiThemeJob job = aiJobs.Latest();
                if (job == null) throw new InvalidOperationException("没有可编译的 AI 创作任务。" );
                AiThemeRevision revision = aiJobs.CurrentCandidate(job.Id);
                MessageBoxResult choice = System.Windows.MessageBox.Show("将把 AI 生成的候选版本 v" + revision.Number + " 校验并导入本地主题库。\n\n不会应用主题，也不会修改 Codex 官方文件。\n\n是否继续？", "确认导入主题", MessageBoxButton.OKCancel, MessageBoxImage.Information);
                if (choice == MessageBoxResult.OK) RunAction("正在导入 AI 主题 v" + revision.Number, "create-recipe", revision.RecipePath, revision.ImagePath);
            }
            catch (Exception ex) { System.Windows.MessageBox.Show(ex.Message, "编译候选", MessageBoxButton.OK, MessageBoxImage.Error); }
        }

        private void RefreshAiJobStatus()
        {
            AiThemeJob job = aiJobs.Latest();
            if (job == null) { aiJobStatus.Text = "尚无本地创作任务。描述视觉方向后创建第一个任务。"; aiCompileCandidateButton.IsEnabled = false; return; }
            int count = job.Revisions == null ? 0 : job.Revisions.Count;
            int imageCount = job.GeneratedImagePaths == null ? 0 : job.GeneratedImagePaths.Count;
            aiJobStatus.Text = "当前任务：" + job.Id + "\n状态：" + job.Stage + " · AI 候选图：" + imageCount + " · 配方版本：" + count + (count > 0 ? "（当前 v" + job.CurrentRevision + "）" : string.Empty);
            aiCompileCandidateButton.IsEnabled = count > 0;
        }

        private static string ExtractJsonObject(string value)
        {
            if (string.IsNullOrWhiteSpace(value)) return null;
            int start = value.IndexOf('{'); int end = value.LastIndexOf('}');
            return start >= 0 && end > start ? value.Substring(start, end - start + 1) : null;
        }

        private void CompileRecipeTheme()
        {
            if (operationCancellation != null) return;
            Microsoft.Win32.OpenFileDialog recipeDialog = new Microsoft.Win32.OpenFileDialog
            {
                Title = "选择 Theme Recipe v1 配方",
                Filter = "Theme Recipe JSON (*.json)|*.json",
                CheckFileExists = true,
                Multiselect = false
            };
            if (recipeDialog.ShowDialog(window) != true) return;
            Microsoft.Win32.OpenFileDialog imageDialog = new Microsoft.Win32.OpenFileDialog
            {
                Title = "选择主题主图",
                Filter = "PNG 或 JPEG 图片|*.png;*.jpg;*.jpeg",
                CheckFileExists = true,
                Multiselect = false
            };
            if (imageDialog.ShowDialog(window) != true) return;
            MessageBoxResult choice = System.Windows.MessageBox.Show(
                "将使用所选配方和主图创建一个新的本地 Theme Pack v2。\n\n不会应用主题，也不会修改 Codex 官方文件。\n\n是否继续？",
                "编译主题配方",
                MessageBoxButton.OKCancel,
                MessageBoxImage.Information);
            if (choice == MessageBoxResult.OK) RunAction("正在编译 Theme Recipe", "create-recipe", recipeDialog.FileName, imageDialog.FileName);
        }

        public void ShowAndActivate()
        {
            if (!window.IsVisible) window.Show();
            if (window.WindowState == WindowState.Minimized) window.WindowState = WindowState.Normal;
            window.Activate(); window.Topmost = true; window.Topmost = false; window.Focus();
        }

        public void OpenPackage(string packagePath)
        {
            ShowAndActivate();
            ImportThemeBundle(packagePath);
        }

        public void RequestExit()
        {
            exitRequested = true; CancelOperation(); window.Close(); System.Windows.Application.Current.Shutdown();
        }

        public void ToggleVisibility()
        {
            if (window.IsVisible && window.WindowState != WindowState.Minimized) window.Hide();
            else ShowAndActivate();
        }

        public bool IsThemePaused { get { return engine.IsPaused; } }
        public string TrayStatusText
        {
            get
            {
                string id = engine.CurrentThemeId;
                return engine.IsPaused ? "官方外观 · 已暂停" : (string.IsNullOrEmpty(id) ? "运行正常" : id + " · 运行中");
            }
        }

        public void RunTrayAction(string command)
        {
            if (string.Equals(command, "pause", StringComparison.OrdinalIgnoreCase)) RunAction("正在暂停主题", "pause");
            else if (string.Equals(command, "resume", StringComparison.OrdinalIgnoreCase)) RunAction("正在重新应用主题", "resume");
            else if (string.Equals(command, "verify", StringComparison.OrdinalIgnoreCase)) RunAction("正在验证运行时", "verify");
        }

        public void Dispose()
        {
            progressTimer.Stop();
            if (operationCancellation != null) operationCancellation.Dispose();
            supervisor.Dispose();
            engine.Dispose();
        }
    }

    internal sealed class StudioTray : IDisposable
    {
        private readonly Forms.NotifyIcon notifyIcon;
        private readonly StudioClient client;
        private readonly Forms.ContextMenuStrip menu;
        private readonly Forms.ToolStripMenuItem statusItem;
        private readonly Forms.ToolStripMenuItem pauseItem;

        public StudioTray(StudioClient client, string iconPath)
        {
            this.client = client;
            notifyIcon = new Forms.NotifyIcon();
            notifyIcon.Text = "Codex Theme Studio";
            notifyIcon.Icon = System.Drawing.Icon.ExtractAssociatedIcon(Forms.Application.ExecutablePath) ??
                (File.Exists(iconPath) ? new System.Drawing.Icon(iconPath) : System.Drawing.SystemIcons.Application);
            menu = new Forms.ContextMenuStrip();
            menu.AutoSize = true;
            menu.MinimumSize = new System.Drawing.Size(248, 0);
            menu.BackColor = System.Drawing.Color.FromArgb(24, 25, 28);
            menu.ForeColor = System.Drawing.Color.FromArgb(242, 243, 245);
            menu.Padding = new Forms.Padding(7, 8, 7, 8);
            menu.ShowImageMargin = false;
            menu.ShowCheckMargin = false;
            menu.Renderer = new StudioMenuRenderer();

            Forms.ToolStripMenuItem brandItem = new Forms.ToolStripMenuItem("Codex Theme Studio");
            brandItem.Enabled = false;
            brandItem.Font = new System.Drawing.Font("Segoe UI", 10F, System.Drawing.FontStyle.Bold);
            statusItem = new Forms.ToolStripMenuItem("● 运行正常");
            statusItem.Enabled = false;
            statusItem.ForeColor = System.Drawing.Color.FromArgb(134, 239, 172);
            menu.Items.Add(brandItem);
            menu.Items.Add(statusItem);
            menu.Items.Add(new Forms.ToolStripSeparator());
            Forms.ToolStripMenuItem openItem = new Forms.ToolStripMenuItem("打开 Theme Studio");
            openItem.Font = new System.Drawing.Font("Segoe UI", 9.5F, System.Drawing.FontStyle.Bold);
            openItem.Click += delegate { client.ShowAndActivate(); };
            pauseItem = new Forms.ToolStripMenuItem("暂停主题");
            pauseItem.Click += delegate { client.RunTrayAction(client.IsThemePaused ? "resume" : "pause"); };
            Forms.ToolStripMenuItem verifyItem = new Forms.ToolStripMenuItem("验证主题运行时");
            verifyItem.Click += delegate { client.RunTrayAction("verify"); };
            Forms.ToolStripMenuItem updateItem = new Forms.ToolStripMenuItem("检查软件更新");
            updateItem.Click += delegate { client.CheckForUpdates(true); };
            Forms.ToolStripMenuItem exitItem = new Forms.ToolStripMenuItem("退出");
            exitItem.Click += delegate { client.RequestExit(); };
            menu.Items.Add(openItem);
            menu.Items.Add(pauseItem);
            menu.Items.Add(verifyItem);
            menu.Items.Add(updateItem);
            menu.Items.Add(new Forms.ToolStripSeparator());
            menu.Items.Add(exitItem);
            foreach (Forms.ToolStripItem item in menu.Items)
            {
                if (!(item is Forms.ToolStripSeparator)) item.Padding = new Forms.Padding(9, 5, 9, 5);
            }
            menu.Opening += delegate
            {
                statusItem.Text = "● " + client.TrayStatusText;
                pauseItem.Text = client.IsThemePaused ? "恢复主题" : "暂停主题";
            };
            notifyIcon.ContextMenuStrip = menu;
            notifyIcon.MouseClick += delegate(object sender, Forms.MouseEventArgs e)
            {
                if (e.Button == Forms.MouseButtons.Left) client.ToggleVisibility();
            };
            notifyIcon.DoubleClick += delegate { client.ShowAndActivate(); };
            notifyIcon.Visible = true;
        }

        public void Dispose()
        {
            notifyIcon.Visible = false;
            menu.Dispose();
            if (notifyIcon.Icon != null) notifyIcon.Icon.Dispose();
            notifyIcon.Dispose();
        }
    }

    internal sealed class StudioMenuRenderer : Forms.ToolStripProfessionalRenderer
    {
        public StudioMenuRenderer() : base(new StudioMenuColorTable()) { RoundedEdges = true; }

        protected override void OnRenderMenuItemBackground(Forms.ToolStripItemRenderEventArgs e)
        {
            if (e.Item.Selected && e.Item.Enabled)
            {
                using (System.Drawing.SolidBrush brush = new System.Drawing.SolidBrush(System.Drawing.Color.FromArgb(47, 49, 54)))
                    e.Graphics.FillRectangle(brush, new System.Drawing.Rectangle(3, 1, e.Item.Width - 6, e.Item.Height - 2));
                return;
            }
            base.OnRenderMenuItemBackground(e);
        }

        protected override void OnRenderSeparator(Forms.ToolStripSeparatorRenderEventArgs e)
        {
            using (System.Drawing.Pen pen = new System.Drawing.Pen(System.Drawing.Color.FromArgb(55, 57, 62)))
                e.Graphics.DrawLine(pen, 10, e.Item.Height / 2, e.Item.Width - 10, e.Item.Height / 2);
        }
    }

    internal sealed class StudioMenuColorTable : Forms.ProfessionalColorTable
    {
        public override System.Drawing.Color ToolStripDropDownBackground { get { return System.Drawing.Color.FromArgb(24, 25, 28); } }
        public override System.Drawing.Color MenuBorder { get { return System.Drawing.Color.FromArgb(62, 64, 70); } }
        public override System.Drawing.Color MenuItemBorder { get { return System.Drawing.Color.Transparent; } }
        public override System.Drawing.Color MenuItemSelected { get { return System.Drawing.Color.FromArgb(47, 49, 54); } }
        public override System.Drawing.Color ImageMarginGradientBegin { get { return System.Drawing.Color.FromArgb(24, 25, 28); } }
        public override System.Drawing.Color ImageMarginGradientMiddle { get { return System.Drawing.Color.FromArgb(24, 25, 28); } }
        public override System.Drawing.Color ImageMarginGradientEnd { get { return System.Drawing.Color.FromArgb(24, 25, 28); } }
    }
}
