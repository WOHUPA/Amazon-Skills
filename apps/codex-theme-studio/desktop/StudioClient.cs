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
    }

    internal sealed class EngineCommandResult
    {
        public int ExitCode;
        public string StandardOutput;
        public string StandardError;
    }

    internal sealed class StudioClient : IDisposable
    {
        private const string AppVersion = "2.6.1";
        private readonly string stateRoot;
        private readonly string engineRoot;
        private readonly NativeThemeEngine engine;
        private readonly UpdateService updateService;
        private readonly JavaScriptSerializer serializer = new JavaScriptSerializer();
        private readonly List<ThemeItem> themes = new List<ThemeItem>();
        private readonly Dictionary<string, BitmapSource> imageCache = new Dictionary<string, BitmapSource>(StringComparer.OrdinalIgnoreCase);
        private readonly DispatcherTimer progressTimer;
        private Window window;
        private ThemeItem selectedTheme;
        private string currentThemeId = string.Empty;
        private string filter = "all";
        private CancellationTokenSource operationCancellation;
        private DateTime operationStartedAt;
        private bool exitRequested;

        private Border titleBar;
        private Image titleIcon;
        private Button minimizeButton;
        private Button maximizeButton;
        private Button closeButton;
        private Button themesNav;
        private Button runtimeNav;
        private Button settingsNav;
        private Grid themesPage;
        private Grid runtimePage;
        private Grid settingsPage;
        private Button createThemeButton;
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
        private TextBlock themeCountLabel;
        private ScrollViewer themeScroll;
        private StackPanel themeStrip;
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
        private Button pauseButton;
        private Button resumeButton;
        private Button runtimeVerifyButton;
        private Button rollbackButton;
        private Button restoreButton;
        private TextBlock themeStorePath;
        private TextBlock enginePath;
        private TextBlock updateStatus;
        private Button checkUpdateButton;

        public StudioClient(string stateRoot, string engineRoot)
        {
            this.stateRoot = stateRoot;
            this.engineRoot = engineRoot;
            engine = new NativeThemeEngine(stateRoot, engineRoot);
            updateService = new UpdateService(stateRoot, engineRoot, AppVersion);
            serializer.MaxJsonLength = 16 * 1024 * 1024;
            LoadWindow();
            BindControls();
            ConfigureWindow();
            progressTimer = new DispatcherTimer(TimeSpan.FromMilliseconds(200), DispatcherPriority.Normal, UpdateProgress, window.Dispatcher);
            progressTimer.Stop();
            window.Loaded += WindowLoaded;
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
            themesNav = Find<Button>("ThemesNav"); runtimeNav = Find<Button>("RuntimeNav"); settingsNav = Find<Button>("SettingsNav");
            themesPage = Find<Grid>("ThemesPage"); runtimePage = Find<Grid>("RuntimePage"); settingsPage = Find<Grid>("SettingsPage");
            createThemeButton = Find<Button>("CreateThemeButton"); searchBox = Find<TextBox>("SearchBox"); searchHint = Find<TextBlock>("SearchHint");
            allFilter = Find<Button>("AllFilter"); darkFilter = Find<Button>("DarkFilter"); lightFilter = Find<Button>("LightFilter");
            heroContent = Find<Grid>("HeroContent"); heroImage = Find<Image>("HeroImage"); heroName = Find<TextBlock>("HeroName");
            heroMeta = Find<TextBlock>("HeroMeta"); heroDescription = Find<TextBlock>("HeroDescription"); heroApplyButton = Find<Button>("HeroApplyButton"); heroPreviewButton = Find<Button>("HeroPreviewButton");
            heroBackgroundButton = Find<Button>("HeroBackgroundButton"); heroDeleteButton = Find<Button>("HeroDeleteButton");
            themeCountLabel = Find<TextBlock>("ThemeCountLabel"); themeScroll = Find<ScrollViewer>("ThemeScroll"); themeStrip = Find<StackPanel>("ThemeStrip");
            scrollLeftButton = Find<Button>("ScrollLeftButton"); scrollRightButton = Find<Button>("ScrollRightButton");
            activityDock = Find<Border>("ActivityDock"); busyBar = Find<ProgressBar>("BusyBar"); operationTitle = Find<TextBlock>("OperationTitle"); progressText = Find<TextBlock>("ProgressText"); cancelOperationButton = Find<Button>("CancelOperationButton");
            runtimeDot = Find<Ellipse>("RuntimeDot"); runtimeLabel = Find<TextBlock>("RuntimeLabel"); currentThemeValue = Find<TextBlock>("CurrentThemeValue"); runtimeModeValue = Find<TextBlock>("RuntimeModeValue");
            pauseButton = Find<Button>("PauseButton"); resumeButton = Find<Button>("ResumeButton"); runtimeVerifyButton = Find<Button>("RuntimeVerifyButton"); rollbackButton = Find<Button>("RollbackButton"); restoreButton = Find<Button>("RestoreButton");
            themeStorePath = Find<TextBlock>("ThemeStorePath"); enginePath = Find<TextBlock>("EnginePath");
            updateStatus = Find<TextBlock>("UpdateStatus"); checkUpdateButton = Find<Button>("CheckUpdateButton");
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
            runtimeNav.Click += delegate { ShowPage("runtime"); };
            settingsNav.Click += delegate { ShowPage("settings"); };
            searchBox.TextChanged += delegate { searchHint.Visibility = string.IsNullOrWhiteSpace(searchBox.Text) ? Visibility.Visible : Visibility.Collapsed; RefreshCards(); };
            allFilter.Click += delegate { filter = "all"; RefreshCards(); };
            darkFilter.Click += delegate { filter = "dark"; RefreshCards(); };
            lightFilter.Click += delegate { filter = "light"; RefreshCards(); };
            scrollLeftButton.Click += delegate { themeScroll.ScrollToHorizontalOffset(Math.Max(0, themeScroll.HorizontalOffset - 444)); };
            scrollRightButton.Click += delegate { themeScroll.ScrollToHorizontalOffset(themeScroll.HorizontalOffset + 444); };
            heroApplyButton.Click += delegate { if (selectedTheme != null) RunAction("正在应用 " + selectedTheme.Name, "activate", selectedTheme.Id, "-RestartExisting"); };
            heroPreviewButton.Click += delegate { ShowPreview(); };
            heroBackgroundButton.Click += delegate { ChooseLocalBackground(); };
            heroDeleteButton.Click += delegate { DeleteSelectedTheme(); };
            createThemeButton.Click += delegate { OpenThemeGenerator(); };
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

        private BitmapSource LoadBitmap(string path)
        {
            if (string.IsNullOrEmpty(path) || !File.Exists(path)) return null;
            DateTime stamp = File.GetLastWriteTimeUtc(path);
            string key = path + "|" + stamp.Ticks;
            BitmapSource cached;
            if (imageCache.TryGetValue(key, out cached)) return cached;
            BitmapImage bitmap = new BitmapImage();
            bitmap.BeginInit(); bitmap.CacheOption = BitmapCacheOption.OnLoad; bitmap.UriSource = new Uri(path); bitmap.EndInit(); bitmap.Freeze();
            if (imageCache.Count >= 64) imageCache.Clear();
            imageCache[key] = bitmap;
            return bitmap;
        }

        private void RefreshState()
        {
            bool paused = File.Exists(Path.Combine(stateRoot, "paused"));
            bool running = false;
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
                        try { Process process = Process.GetProcessById(pid); running = !process.HasExited; process.Dispose(); } catch { }
                    }
                }
                catch { currentThemeId = string.Empty; }
            }
            if (!running)
            {
                using (TcpClient client = new TcpClient())
                {
                    try
                    {
                        IAsyncResult connection = client.BeginConnect("127.0.0.1", 9335, null, null);
                        if (connection.AsyncWaitHandle.WaitOne(180))
                        {
                            client.EndConnect(connection);
                            running = client.Connected;
                        }
                        connection.AsyncWaitHandle.Close();
                    }
                    catch { running = false; }
                }
            }
            ThemeItem current = themes.FirstOrDefault(delegate(ThemeItem item) { return string.Equals(item.Id, currentThemeId, StringComparison.Ordinal); });
            runtimeLabel.Text = running ? "运行时正常" : "运行时未连接";
            runtimeDot.Fill = Brush(running ? "#50C989" : "#D8A757");
            currentThemeValue.Text = current == null ? "官方外观" : current.Name;
            runtimeModeValue.Text = paused ? "已暂停" : (running ? "主题运行中" : "未连接");
            if (selectedTheme == null) selectedTheme = current ?? themes.FirstOrDefault();
            RefreshCards();
            SetHero(selectedTheme);
        }

        private void RefreshCards()
        {
            if (themeStrip == null) return;
            double offset = themeScroll.HorizontalOffset;
            string query = (searchBox.Text ?? string.Empty).Trim();
            List<ThemeItem> visible = themes.Where(delegate(ThemeItem item)
            {
                bool filterMatch = filter == "all" || string.Equals(item.Appearance, filter, StringComparison.OrdinalIgnoreCase);
                bool queryMatch = query.Length == 0 || (item.Name + " " + item.Id).IndexOf(query, StringComparison.OrdinalIgnoreCase) >= 0;
                return filterMatch && queryMatch;
            }).ToList();
            if (selectedTheme == null || !visible.Any(delegate(ThemeItem item) { return item.Id == selectedTheme.Id; })) selectedTheme = visible.FirstOrDefault();
            themeStrip.Children.Clear();
            foreach (ThemeItem item in visible) themeStrip.Children.Add(CreateCard(item));
            themeCountLabel.Text = "· " + visible.Count + " / " + themes.Count;
            SetFilterStyle(allFilter, filter == "all"); SetFilterStyle(darkFilter, filter == "dark"); SetFilterStyle(lightFilter, filter == "light");
            themeScroll.ScrollToHorizontalOffset(offset);
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
            Border card = new Border(); card.Width = 208; card.Height = 164; card.Margin = new Thickness(0, 0, 14, 0); card.CornerRadius = new CornerRadius(11); card.Cursor = Cursors.Hand;
            card.Background = Brush("#111318"); card.BorderThickness = new Thickness(selectedTheme != null && selectedTheme.Id == item.Id ? 2 : 1);
            card.BorderBrush = Brush(selectedTheme != null && selectedTheme.Id == item.Id ? "#D6AE78" : "#34312E");
            Grid layout = new Grid(); layout.RowDefinitions.Add(new RowDefinition { Height = new GridLength(118) }); layout.RowDefinitions.Add(new RowDefinition());
            layout.SizeChanged += delegate { ApplyRoundedClip(layout, 10); };
            Grid visual = new Grid(); Image image = new Image(); image.Source = LoadBitmap(item.BackgroundPath); image.Stretch = Stretch.UniformToFill; visual.Children.Add(image);
            if (item.Id == currentThemeId)
            {
                Border badge = new Border { Background = Brush("#E7C18D"), CornerRadius = new CornerRadius(8), Padding = new Thickness(8, 3, 8, 3), HorizontalAlignment = HorizontalAlignment.Right, VerticalAlignment = VerticalAlignment.Top, Margin = new Thickness(8) };
                badge.Child = new TextBlock { Text = "当前", Foreground = Brush("#1A120A"), FontSize = 10, FontWeight = FontWeights.SemiBold }; visual.Children.Add(badge);
            }
            Grid.SetRow(visual, 0); layout.Children.Add(visual);
            TextBlock title = new TextBlock { Text = item.Name, FontSize = 13, FontWeight = FontWeights.SemiBold, Foreground = Brush("#F0E1CE"), Margin = new Thickness(12, 0, 12, 0), VerticalAlignment = VerticalAlignment.Center, TextTrimming = TextTrimming.CharacterEllipsis };
            Grid.SetRow(title, 1); layout.Children.Add(title); card.Child = layout;
            card.MouseLeftButtonUp += delegate { selectedTheme = item; SetHero(item); RefreshCards(); };
            return card;
        }

        private void SetHero(ThemeItem item)
        {
            if (item == null) return;
            selectedTheme = item; heroImage.Source = LoadBitmap(item.BackgroundPath); heroName.Text = item.Name;
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
            runtimePage.Visibility = page == "runtime" ? Visibility.Visible : Visibility.Collapsed;
            settingsPage.Visibility = page == "settings" ? Visibility.Visible : Visibility.Collapsed;
            SetNavStyle(themesNav, page == "themes"); SetNavStyle(runtimeNav, page == "runtime"); SetNavStyle(settingsNav, page == "settings");
        }

        private static void SetNavStyle(Button button, bool active)
        {
            button.Background = Brush(active ? "#181718" : "Transparent"); button.BorderBrush = Brush(active ? "#D6AE78" : "Transparent"); button.Foreground = Brush(active ? "#F1D5AE" : "#BDB5AB");
        }

        private void SetBusy(bool busy, string label)
        {
            activityDock.Visibility = busy ? Visibility.Visible : Visibility.Collapsed; operationTitle.Text = label;
            foreach (Button button in new[] { createThemeButton, heroApplyButton, heroBackgroundButton, heroDeleteButton, pauseButton, resumeButton, runtimeVerifyButton, rollbackButton, restoreButton }) button.IsEnabled = !busy;
            if (busy) { busyBar.Value = 4; progressText.Text = " · 4%"; cancelOperationButton.IsEnabled = true; }
            else SetHero(selectedTheme);
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
                 (string.Equals(arguments[0], "set-background", StringComparison.OrdinalIgnoreCase) && arguments.Length > 1 && string.Equals(arguments[1], currentThemeId, StringComparison.Ordinal))) &&
                engine.RequiresCodexRestart())
            {
                MessageBoxResult restart = System.Windows.MessageBox.Show(
                    "Codex 需要重启一次以建立安全的本机主题连接。未保存的输入可能丢失，是否继续？",
                    "Codex Theme Studio",
                    MessageBoxButton.OKCancel,
                    MessageBoxImage.Warning);
                if (restart != MessageBoxResult.OK) return;
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
                if (command == "set-background" || command == "delete") LoadThemes();
                RefreshState();
                if (command == "set-background") System.Windows.MessageBox.Show("本地背景已保存，并同时用于首页与任务页。", "Codex Theme Studio", MessageBoxButton.OK, MessageBoxImage.Information);
                if (command == "delete") System.Windows.MessageBox.Show("主题已从主题库删除，并保留了本地可恢复备份。", "Codex Theme Studio", MessageBoxButton.OK, MessageBoxImage.Information);
            }
            catch (OperationCanceledException) { }
            catch (TimeoutException ex) { System.Windows.MessageBox.Show(ex.Message, "Codex Theme Studio", MessageBoxButton.OK, MessageBoxImage.Warning); }
            catch (Exception ex) { System.Windows.MessageBox.Show(ex.Message, "Codex Theme Studio", MessageBoxButton.OK, MessageBoxImage.Error); }
            finally
            {
                progressTimer.Stop();
                if (operationCancellation != null) { operationCancellation.Dispose(); operationCancellation = null; }
                SetBusy(false, string.Empty);
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
            Grid grid = new Grid(); Image image = new Image { Source = LoadBitmap(selectedTheme.BackgroundPath), Stretch = Stretch.UniformToFill }; grid.Children.Add(image);
            Border panel = new Border { Width = 420, HorizontalAlignment = HorizontalAlignment.Left, Margin = new Thickness(38), Padding = new Thickness(28), CornerRadius = new CornerRadius(16), Background = Brush("#E6121418") };
            StackPanel stack = new StackPanel(); stack.Children.Add(new TextBlock { Text = selectedTheme.Name, FontSize = 30, Foreground = Brush("#F4DFC1"), Margin = new Thickness(0, 0, 0, 14) }); stack.Children.Add(new TextBlock { Text = selectedTheme.Id, FontSize = 12, Foreground = Brush("#B8B0A6") }); panel.Child = stack; grid.Children.Add(panel); preview.Content = grid; preview.ShowDialog();
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

        public void ShowAndActivate()
        {
            if (!window.IsVisible) window.Show();
            if (window.WindowState == WindowState.Minimized) window.WindowState = WindowState.Normal;
            window.Activate(); window.Topmost = true; window.Topmost = false; window.Focus();
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
