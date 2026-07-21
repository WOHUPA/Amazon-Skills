[CmdletBinding()]
param([int]$Port = 9335)

$ErrorActionPreference = 'Stop'
if (-not ('CodexThemeStudioDpi' -as [type])) {
  Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class CodexThemeStudioDpi {
  [DllImport("user32.dll")]
  public static extern bool SetProcessDpiAwarenessContext(IntPtr value);
  [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
  public static extern int SetCurrentProcessExplicitAppUserModelID(string appId);
}
'@
}
try { [void][CodexThemeStudioDpi]::SetProcessDpiAwarenessContext([IntPtr](-4)) } catch { }
try { [void][CodexThemeStudioDpi]::SetCurrentProcessExplicitAppUserModelID('CodexThemeStudio.Desktop') } catch { }
Add-Type -AssemblyName PresentationFramework
Add-Type -AssemblyName PresentationCore
Add-Type -AssemblyName WindowsBase

. (Join-Path $PSScriptRoot 'common-windows.ps1')
. (Join-Path $PSScriptRoot 'theme-windows.ps1')

Assert-DreamSkinPort -Port $Port
$StateRoot = Join-Path $env:LOCALAPPDATA 'CodexThemeStudio'
$StudioCli = Join-Path $PSScriptRoot 'theme-studio.ps1'
$ThemePaths = Get-DreamSkinThemePaths -StateRoot $StateRoot
$PowerShellExe = (Get-Command powershell.exe -ErrorAction Stop).Source

[xml]$xaml = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        xmlns:shell="clr-namespace:System.Windows.Shell;assembly=PresentationFramework"
        Title="Codex Theme Studio" Width="1380" Height="840" MinWidth="1120" MinHeight="720"
        WindowStartupLocation="CenterScreen" WindowStyle="None" ResizeMode="CanResize"
        BorderThickness="0" SnapsToDevicePixels="True" UseLayoutRounding="True"
        Background="#0A0C10" Foreground="#F5E8D4" FontFamily="Microsoft YaHei UI">
  <shell:WindowChrome.WindowChrome>
    <shell:WindowChrome CaptionHeight="0" ResizeBorderThickness="7" GlassFrameThickness="0" CornerRadius="0" UseAeroCaptionButtons="False"/>
  </shell:WindowChrome.WindowChrome>
  <Window.Resources>
    <SolidColorBrush x:Key="Canvas" Color="#0A0C10"/>
    <SolidColorBrush x:Key="Surface" Color="#111318"/>
    <SolidColorBrush x:Key="SurfaceRaised" Color="#17191F"/>
    <SolidColorBrush x:Key="Border" Color="#2C2B2A"/>
    <SolidColorBrush x:Key="Muted" Color="#A7A09A"/>
    <SolidColorBrush x:Key="Gold" Color="#D6AE78"/>
    <SolidColorBrush x:Key="GoldSoft" Color="#F1D5AE"/>
    <SolidColorBrush x:Key="Success" Color="#50C989"/>
    <Style x:Key="ActionButton" TargetType="Button">
      <Setter Property="Foreground" Value="#EEE4D7"/>
      <Setter Property="Background" Value="#17191D"/>
      <Setter Property="BorderBrush" Value="#3A3733"/>
      <Setter Property="BorderThickness" Value="1"/>
      <Setter Property="Padding" Value="18,10"/>
      <Setter Property="MinHeight" Value="44"/>
      <Setter Property="Cursor" Value="Hand"/>
      <Setter Property="FontSize" Value="14"/>
      <Setter Property="Template"><Setter.Value><ControlTemplate TargetType="Button">
        <Border x:Name="ButtonBorder" Background="{TemplateBinding Background}" BorderBrush="{TemplateBinding BorderBrush}"
                BorderThickness="{TemplateBinding BorderThickness}" CornerRadius="10" Padding="{TemplateBinding Padding}">
          <ContentPresenter HorizontalAlignment="Center" VerticalAlignment="Center"/>
        </Border>
        <ControlTemplate.Triggers>
          <Trigger Property="IsMouseOver" Value="True"><Setter TargetName="ButtonBorder" Property="Background" Value="#212329"/><Setter TargetName="ButtonBorder" Property="BorderBrush" Value="#5B5146"/></Trigger>
          <Trigger Property="IsKeyboardFocused" Value="True"><Setter TargetName="ButtonBorder" Property="BorderBrush" Value="#D6AE78"/><Setter TargetName="ButtonBorder" Property="BorderThickness" Value="2"/></Trigger>
          <Trigger Property="IsEnabled" Value="False"><Setter TargetName="ButtonBorder" Property="Opacity" Value="0.45"/></Trigger>
        </ControlTemplate.Triggers>
      </ControlTemplate></Setter.Value></Setter>
    </Style>
    <Style x:Key="PrimaryButton" TargetType="Button" BasedOn="{StaticResource ActionButton}">
      <Setter Property="Foreground" Value="#1A120A"/>
      <Setter Property="Background" Value="#E7C18D"/>
      <Setter Property="BorderBrush" Value="#F3D6AE"/>
      <Setter Property="FontWeight" Value="SemiBold"/>
      <Style.Triggers><Trigger Property="IsMouseOver" Value="True"><Setter Property="Background" Value="#F2D4AA"/></Trigger></Style.Triggers>
    </Style>
    <Style x:Key="DangerButton" TargetType="Button" BasedOn="{StaticResource ActionButton}">
      <Setter Property="Foreground" Value="#F0D8BB"/><Setter Property="BorderBrush" Value="#765F45"/>
    </Style>
    <Style x:Key="RailButton" TargetType="Button">
      <Setter Property="Foreground" Value="#BDB5AB"/><Setter Property="Background" Value="Transparent"/>
      <Setter Property="BorderBrush" Value="Transparent"/><Setter Property="BorderThickness" Value="2,0,0,0"/>
      <Setter Property="Height" Value="88"/><Setter Property="HorizontalContentAlignment" Value="Center"/>
      <Setter Property="Cursor" Value="Hand"/><Setter Property="Template"><Setter.Value><ControlTemplate TargetType="Button">
        <Border x:Name="RailBackground" Background="{TemplateBinding Background}" BorderBrush="{TemplateBinding BorderBrush}" BorderThickness="{TemplateBinding BorderThickness}">
          <ContentPresenter HorizontalAlignment="Center" VerticalAlignment="Center"/>
        </Border>
        <ControlTemplate.Triggers>
          <Trigger Property="IsMouseOver" Value="True"><Setter TargetName="RailBackground" Property="Background" Value="#17171A"/></Trigger>
          <Trigger Property="IsKeyboardFocused" Value="True"><Setter TargetName="RailBackground" Property="BorderBrush" Value="#D6AE78"/></Trigger>
        </ControlTemplate.Triggers>
      </ControlTemplate></Setter.Value></Setter>
    </Style>
    <Style x:Key="FilterButton" TargetType="Button" BasedOn="{StaticResource ActionButton}">
      <Setter Property="MinHeight" Value="38"/><Setter Property="Padding" Value="16,6"/><Setter Property="FontSize" Value="13"/>
    </Style>
    <Style x:Key="WindowButton" TargetType="Button">
      <Setter Property="Foreground" Value="#CFC8BE"/><Setter Property="Background" Value="Transparent"/><Setter Property="BorderThickness" Value="0"/>
      <Setter Property="FontFamily" Value="Segoe Fluent Icons"/><Setter Property="FontSize" Value="12"/>
      <Setter Property="Cursor" Value="Hand"/>
    </Style>
  </Window.Resources>
  <Grid>
    <Grid.RowDefinitions><RowDefinition Height="52"/><RowDefinition Height="*"/></Grid.RowDefinitions>
    <Border x:Name="TitleBar" Grid.Row="0" Background="#0D0F13" BorderBrush="#252529" BorderThickness="0,0,0,1">
      <Grid><Grid.ColumnDefinitions><ColumnDefinition/><ColumnDefinition Width="48"/><ColumnDefinition Width="48"/><ColumnDefinition Width="48"/></Grid.ColumnDefinitions>
        <StackPanel Orientation="Horizontal" VerticalAlignment="Center" Margin="24,0">
          <Image x:Name="TitleIcon" Width="24" Height="24" Stretch="Uniform" Margin="0,0,12,0"/>
          <TextBlock Text="Codex Theme Studio" Foreground="#F4E7D4" FontFamily="Segoe UI Variable Display" FontWeight="SemiBold" FontSize="17"/>
        </StackPanel>
        <Button x:Name="MinimizeButton" Grid.Column="1" Content="&#xE921;" Style="{StaticResource WindowButton}"/>
        <Button x:Name="MaximizeButton" Grid.Column="2" Content="&#xE922;" Style="{StaticResource WindowButton}"/>
        <Button x:Name="CloseButton" Grid.Column="3" Content="&#xE8BB;" Style="{StaticResource WindowButton}"/>
      </Grid>
    </Border>

    <Grid Grid.Row="1">
      <Grid.ColumnDefinitions><ColumnDefinition Width="132"/><ColumnDefinition Width="*"/></Grid.ColumnDefinitions>
      <Border Grid.Column="0" Background="#0D0F13" BorderBrush="#252529" BorderThickness="0,0,1,0">
        <Grid><Grid.RowDefinitions><RowDefinition Height="22"/><RowDefinition Height="*"/><RowDefinition Height="104"/></Grid.RowDefinitions>
          <StackPanel Grid.Row="1">
            <Button x:Name="ThemesNav" Style="{StaticResource RailButton}" Background="#181718" BorderBrush="#D6AE78" Foreground="#F1D5AE">
              <StackPanel><TextBlock Text="&#xE8B9;" FontFamily="Segoe Fluent Icons" FontSize="24" HorizontalAlignment="Center"/><TextBlock Text="主题" FontSize="15" Margin="0,9,0,0" HorizontalAlignment="Center"/></StackPanel>
            </Button>
            <Button x:Name="RuntimeNav" Style="{StaticResource RailButton}">
              <StackPanel><TextBlock Text="&#xE9D9;" FontFamily="Segoe Fluent Icons" FontSize="24" HorizontalAlignment="Center"/><TextBlock Text="运行" FontSize="15" Margin="0,9,0,0" HorizontalAlignment="Center"/></StackPanel>
            </Button>
            <Button x:Name="SettingsNav" Style="{StaticResource RailButton}">
              <StackPanel><TextBlock Text="&#xE713;" FontFamily="Segoe Fluent Icons" FontSize="24" HorizontalAlignment="Center"/><TextBlock Text="设置" FontSize="15" Margin="0,9,0,0" HorizontalAlignment="Center"/></StackPanel>
            </Button>
          </StackPanel>
          <StackPanel Grid.Row="2" Margin="16,0,12,18" VerticalAlignment="Bottom">
            <StackPanel Orientation="Horizontal"><Ellipse x:Name="RuntimeDot" Width="9" Height="9" Fill="#50C989" Margin="0,0,8,0"/><TextBlock x:Name="RuntimeLabel" Text="运行时正常" FontSize="12" Foreground="#C5BDB2"/></StackPanel>
            <TextBlock Text="CDP 9335" Foreground="#7E7973" FontSize="11" Margin="17,6,0,0"/>
          </StackPanel>
        </Grid>
      </Border>

      <Grid Grid.Column="1" Margin="34,24,34,22">
        <Grid x:Name="ThemesPage">
          <Grid.RowDefinitions><RowDefinition Height="82"/><RowDefinition Height="54"/><RowDefinition Height="286"/><RowDefinition Height="52"/><RowDefinition Height="*"/><RowDefinition Height="Auto"/></Grid.RowDefinitions>
          <Grid Grid.Row="0"><Grid.ColumnDefinitions><ColumnDefinition/><ColumnDefinition Width="Auto"/></Grid.ColumnDefinitions>
            <StackPanel>
              <TextBlock Text="选择你的工作氛围" Foreground="#F2DAB9" FontFamily="Microsoft YaHei UI" FontWeight="SemiBold" FontSize="34"/>
              <TextBlock Text="精心设计的主题，为创作注入灵感与专注。" Foreground="#9B9389" FontSize="14" Margin="0,9,0,0"/>
            </StackPanel>
            <Button x:Name="CreateThemeButton" Grid.Column="1" Style="{StaticResource ActionButton}" VerticalAlignment="Top" Padding="20,9">
              <StackPanel Orientation="Horizontal"><TextBlock Text="&#xE710;" FontFamily="Segoe Fluent Icons" Foreground="#D6AE78" FontSize="16" Margin="0,0,9,0"/><TextBlock Text="创建主题"/></StackPanel>
            </Button>
          </Grid>

          <Grid Grid.Row="1"><Grid.ColumnDefinitions><ColumnDefinition Width="360"/><ColumnDefinition/><ColumnDefinition Width="Auto"/></Grid.ColumnDefinitions>
            <Border Background="#121419" BorderBrush="#302E2C" BorderThickness="1" CornerRadius="20" Height="42" VerticalAlignment="Top">
              <Grid><Grid.ColumnDefinitions><ColumnDefinition Width="44"/><ColumnDefinition/></Grid.ColumnDefinitions>
                <TextBlock Text="&#xE721;" FontFamily="Segoe Fluent Icons" Foreground="#817B74" FontSize="15" HorizontalAlignment="Center" VerticalAlignment="Center"/>
                <TextBox x:Name="SearchBox" Grid.Column="1" Background="Transparent" BorderThickness="0" Foreground="#EEE4D7" CaretBrush="#D6AE78" VerticalContentAlignment="Center" FontSize="14" Padding="0,0,14,0"/>
                <TextBlock x:Name="SearchHint" Grid.Column="1" Text="搜索主题" Foreground="#736E68" FontSize="14" VerticalAlignment="Center" IsHitTestVisible="False"/>
              </Grid>
            </Border>
            <StackPanel Grid.Column="2" Orientation="Horizontal" VerticalAlignment="Top">
              <Button x:Name="AllFilter" Content="全部" Style="{StaticResource FilterButton}" Margin="0,0,7,0"/>
              <Button x:Name="DarkFilter" Content="深色" Style="{StaticResource FilterButton}" Margin="0,0,7,0"/>
              <Button x:Name="LightFilter" Content="浅色" Style="{StaticResource FilterButton}"/>
            </StackPanel>
          </Grid>

          <Border x:Name="HeroFrame" Grid.Row="2" Background="#101216" BorderBrush="#34302C" BorderThickness="1" CornerRadius="16">
            <Grid x:Name="HeroContent">
              <Image x:Name="HeroImage" Stretch="UniformToFill" HorizontalAlignment="Stretch" VerticalAlignment="Stretch"/>
              <Border Width="540" HorizontalAlignment="Left" Background="#E80D0F13">
                <StackPanel Margin="38,30,28,26" VerticalAlignment="Center">
                  <TextBlock x:Name="HeroName" Text="主题" Foreground="#F4DFC1" FontWeight="SemiBold" FontSize="34" TextTrimming="CharacterEllipsis"/>
                  <TextBlock x:Name="HeroMeta" Text="深色 · 原生布局" Foreground="#C9B89F" FontSize="12" Margin="0,10,0,0"/>
                  <TextBlock x:Name="HeroDescription" Text="为长时间创作提供舒适、沉浸的视觉体验。" Foreground="#A9A097" FontSize="14" TextWrapping="Wrap" Width="430" HorizontalAlignment="Left" Margin="0,18,0,0" LineHeight="23"/>
                  <StackPanel Orientation="Horizontal" Margin="0,23,0,0">
                    <Button x:Name="HeroApplyButton" Content="应用主题" Style="{StaticResource PrimaryButton}" MinWidth="148" Margin="0,0,10,0"/>
                    <Button x:Name="HeroPreviewButton" Content="预览" Style="{StaticResource ActionButton}" MinWidth="92"/>
                  </StackPanel>
                </StackPanel>
              </Border>
            </Grid>
          </Border>

          <Grid Grid.Row="3"><Grid.ColumnDefinitions><ColumnDefinition/><ColumnDefinition Width="Auto"/></Grid.ColumnDefinitions>
            <StackPanel Orientation="Horizontal" VerticalAlignment="Center"><TextBlock Text="主题库" Foreground="#E8D2B3" FontSize="18" FontWeight="SemiBold"/><TextBlock x:Name="ThemeCountLabel" Text=" · 12" Foreground="#8D867D" FontSize="14" VerticalAlignment="Bottom" Margin="8,0,0,2"/></StackPanel>
            <StackPanel Grid.Column="1" Orientation="Horizontal" VerticalAlignment="Center">
              <Button x:Name="ScrollLeftButton" Content="&#xE76B;" FontFamily="Segoe Fluent Icons" Style="{StaticResource ActionButton}" Padding="12,6" MinHeight="36" Margin="0,0,7,0"/>
              <Button x:Name="ScrollRightButton" Content="&#xE76C;" FontFamily="Segoe Fluent Icons" Style="{StaticResource ActionButton}" Padding="12,6" MinHeight="36"/>
            </StackPanel>
          </Grid>

          <ScrollViewer x:Name="ThemeScroll" Grid.Row="4" HorizontalScrollBarVisibility="Hidden" VerticalScrollBarVisibility="Disabled" CanContentScroll="False">
            <StackPanel x:Name="ThemeStrip" Orientation="Horizontal"/>
          </ScrollViewer>

          <Border x:Name="ActivityDock" Grid.Row="5" Visibility="Collapsed" Background="#15171B" BorderBrush="#45403A" BorderThickness="1" CornerRadius="14" Padding="20,14" Margin="0,14,0,0">
            <Grid><Grid.ColumnDefinitions><ColumnDefinition Width="Auto"/><ColumnDefinition/><ColumnDefinition Width="Auto"/><ColumnDefinition Width="Auto"/></Grid.ColumnDefinitions>
              <TextBlock Text="&#xE895;" FontFamily="Segoe Fluent Icons" Foreground="#D6AE78" FontSize="30" VerticalAlignment="Center" Margin="0,0,18,0"/>
              <StackPanel Grid.Column="1" VerticalAlignment="Center">
                <StackPanel Orientation="Horizontal"><TextBlock x:Name="OperationTitle" Text="正在应用主题" Foreground="#F0DEC5" FontSize="15" FontWeight="SemiBold"/><TextBlock x:Name="ProgressText" Text=" · 0%" Foreground="#C8B08F" FontSize="15"/></StackPanel>
                <ProgressBar x:Name="BusyBar" Height="5" Minimum="0" Maximum="100" Value="0" Foreground="#D6AE78" Background="#2A2928" Margin="0,10,24,0"/>
              </StackPanel>
              <TextBlock x:Name="ElapsedText" Grid.Column="2" Text="已用时 00:00" Foreground="#8F8982" FontSize="12" VerticalAlignment="Center" Margin="18,0,24,0"/>
              <Button x:Name="CancelOperationButton" Grid.Column="3" Content="取消" Style="{StaticResource DangerButton}" MinWidth="116" VerticalAlignment="Center"/>
            </Grid>
          </Border>
        </Grid>

        <Grid x:Name="RuntimePage" Visibility="Collapsed">
          <Grid.RowDefinitions><RowDefinition Height="92"/><RowDefinition Height="*"/></Grid.RowDefinitions>
          <StackPanel><TextBlock Text="运行状态" Foreground="#F2DAB9" FontSize="34" FontWeight="SemiBold"/><TextBlock Text="Theme Studio 的验证、注入和回退链路。" Foreground="#9B9389" FontSize="14" Margin="0,9,0,0"/></StackPanel>
          <Grid Grid.Row="1"><Grid.ColumnDefinitions><ColumnDefinition/><ColumnDefinition/></Grid.ColumnDefinitions>
            <Border Background="#111318" BorderBrush="#302E2C" BorderThickness="1" CornerRadius="16" Padding="28" Margin="0,0,12,0" VerticalAlignment="Top">
              <StackPanel><TextBlock Text="当前会话" Foreground="#D6AE78" FontSize="13"/><TextBlock x:Name="CurrentThemeValue" Text="—" FontSize="28" FontWeight="SemiBold" Margin="0,18,0,0"/><TextBlock x:Name="RuntimeModeValue" Text="—" Foreground="#A79F95" FontSize="14" Margin="0,8,0,0"/><TextBlock Text="CDP 端口 9335" Foreground="#756F68" FontSize="12" Margin="0,22,0,0"/></StackPanel>
            </Border>
            <Border Grid.Column="1" Background="#111318" BorderBrush="#302E2C" BorderThickness="1" CornerRadius="16" Padding="28" Margin="12,0,0,0" VerticalAlignment="Top">
              <StackPanel><TextBlock Text="安全操作" Foreground="#D6AE78" FontSize="13"/><TextBlock Text="所有动作都使用事务、验证与可恢复回退。" Foreground="#A79F95" FontSize="14" Margin="0,16,0,22" TextWrapping="Wrap"/>
                <WrapPanel><Button x:Name="PauseButton" Content="暂停主题" Style="{StaticResource ActionButton}" Margin="0,0,8,8"/><Button x:Name="ResumeButton" Content="重新应用" Style="{StaticResource PrimaryButton}" Margin="0,0,8,8"/><Button x:Name="RuntimeVerifyButton" Content="运行验证" Style="{StaticResource ActionButton}" Margin="0,0,8,8"/><Button x:Name="RollbackButton" Content="回退" Style="{StaticResource ActionButton}" Margin="0,0,8,8"/><Button x:Name="RestoreButton" Content="恢复官方" Style="{StaticResource ActionButton}" Margin="0,0,8,8"/></WrapPanel>
              </StackPanel>
            </Border>
          </Grid>
        </Grid>

        <Grid x:Name="SettingsPage" Visibility="Collapsed">
          <Grid.RowDefinitions><RowDefinition Height="92"/><RowDefinition Height="*"/></Grid.RowDefinitions>
          <StackPanel><TextBlock Text="设置" Foreground="#F2DAB9" FontSize="34" FontWeight="SemiBold"/><TextBlock Text="运行时位置与本机安全边界。" Foreground="#9B9389" FontSize="14" Margin="0,9,0,0"/></StackPanel>
          <Border Grid.Row="1" Background="#111318" BorderBrush="#302E2C" BorderThickness="1" CornerRadius="16" Padding="30" VerticalAlignment="Top">
            <StackPanel><TextBlock Text="本机存储" Foreground="#F0DEC5" FontSize="20" FontWeight="SemiBold"/><TextBlock Text="主题仓库" Foreground="#9C9388" FontSize="12" Margin="0,24,0,6"/><TextBlock x:Name="ThemeStorePath" Text="" Foreground="#DED3C5" FontSize="14" TextWrapping="Wrap"/><TextBlock Text="运行时引擎" Foreground="#9C9388" FontSize="12" Margin="0,22,0,6"/><TextBlock x:Name="EnginePath" Text="" Foreground="#DED3C5" FontSize="14" TextWrapping="Wrap"/>
              <Border Background="#161812" BorderBrush="#48523C" BorderThickness="1" CornerRadius="12" Padding="16" Margin="0,26,0,0"><TextBlock Text="Theme Pack v2 只加载白名单数据与静态资产，不修改 WindowsApps、app.asar、签名或认证数据。" Foreground="#B9D4AA" TextWrapping="Wrap" FontSize="13"/></Border>
            </StackPanel>
          </Border>
        </Grid>
        <TextBlock x:Name="StatusText" Text="就绪" Visibility="Collapsed"/>
      </Grid>
    </Grid>
  </Grid>
</Window>
'@

$reader = New-Object System.Xml.XmlNodeReader $xaml
$Window = [Windows.Markup.XamlReader]::Load($reader)
$names = @(
  'TitleBar','TitleIcon','MinimizeButton','MaximizeButton','CloseButton','ThemesNav','RuntimeNav','SettingsNav',
  'ThemesPage','RuntimePage','SettingsPage','CreateThemeButton','SearchBox','SearchHint','AllFilter','DarkFilter','LightFilter',
  'HeroFrame','HeroContent','HeroImage','HeroName','HeroMeta','HeroDescription','HeroApplyButton','HeroPreviewButton','ThemeCountLabel','ThemeScroll','ThemeStrip',
  'ScrollLeftButton','ScrollRightButton','ActivityDock','BusyBar','OperationTitle','ProgressText','ElapsedText','CancelOperationButton',
  'RuntimeDot','RuntimeLabel','CurrentThemeValue','RuntimeModeValue','PauseButton','ResumeButton','RuntimeVerifyButton','RollbackButton','RestoreButton',
  'ThemeStorePath','EnginePath','StatusText'
)
foreach ($name in $names) { Set-Variable -Name $name -Value $Window.FindName($name) -Scope Script }

$script:Themes = @()
$script:Filter = 'all'
$script:SelectedItem = $null
$script:ActiveOperation = $null
$script:BitmapCache = @{}
$StudioIconPath = Join-Path (Split-Path -Parent $PSScriptRoot) 'assets\studio.ico'

if (Test-Path -LiteralPath $StudioIconPath -PathType Leaf) {
  try {
    $iconFrame = [Windows.Media.Imaging.BitmapFrame]::Create(
      [Uri]::new($StudioIconPath),
      [Windows.Media.Imaging.BitmapCreateOptions]::PreservePixelFormat,
      [Windows.Media.Imaging.BitmapCacheOption]::OnLoad
    )
    $iconFrame.Freeze()
    $Window.Icon = $iconFrame
    $TitleIcon.Source = $iconFrame
  } catch { }
}

function Update-HeroClip {
  if ($HeroContent.ActualWidth -le 0 -or $HeroContent.ActualHeight -le 0) { return }
  $clip = [Windows.Media.RectangleGeometry]::new()
  $clip.Rect = [Windows.Rect]::new(0, 0, $HeroContent.ActualWidth, $HeroContent.ActualHeight)
  $clip.RadiusX = 15
  $clip.RadiusY = 15
  $HeroContent.Clip = $clip
}

function Add-StudioRoundedClip([Windows.FrameworkElement]$Element, [double]$Radius) {
  $Element.Add_SizeChanged({
    param($sender, $eventArgs)
    if ($sender.ActualWidth -le 0 -or $sender.ActualHeight -le 0) { return }
    $geometry = [Windows.Media.RectangleGeometry]::new()
    $geometry.Rect = [Windows.Rect]::new(0, 0, $sender.ActualWidth, $sender.ActualHeight)
    $geometry.RadiusX = $Radius
    $geometry.RadiusY = $Radius
    $sender.Clip = $geometry
  }.GetNewClosure())
}

function Get-StudioBitmap([string]$Path) {
  if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
  $fullPath = [IO.Path]::GetFullPath($Path)
  $cacheKey = $fullPath + '|' + (Get-Item -LiteralPath $fullPath).LastWriteTimeUtc.Ticks
  if ($script:BitmapCache.ContainsKey($cacheKey)) { return $script:BitmapCache[$cacheKey] }
  $bitmap = [Windows.Media.Imaging.BitmapImage]::new()
  $bitmap.BeginInit()
  $bitmap.CacheOption = [Windows.Media.Imaging.BitmapCacheOption]::OnLoad
  $bitmap.UriSource = [Uri]$fullPath
  $bitmap.EndInit()
  $bitmap.Freeze()
  if ($script:BitmapCache.Count -ge 64) { $script:BitmapCache.Clear() }
  $script:BitmapCache[$cacheKey] = $bitmap
  return $bitmap
}

function Get-StudioUiState {
  $state = $null
  if (Test-Path -LiteralPath $ThemePaths.State -PathType Leaf) {
    try { $state = Read-DreamSkinState -Path $ThemePaths.State } catch { }
  }
  $paused = Test-DreamSkinPaused -StateRoot $StateRoot
  $currentId = if ($state -and $state.currentThemeId) { "$($state.currentThemeId)" } else { '' }
  $watcherRunning = $false
  if ($state -and $state.injectorPid) {
    $watcherRunning = $null -ne (Get-Process -Id ([int]$state.injectorPid) -ErrorAction SilentlyContinue)
  }
  if (-not $watcherRunning) {
    $client = [Net.Sockets.TcpClient]::new()
    try {
      $connect = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
      if ($connect.AsyncWaitHandle.WaitOne(180)) {
        $client.EndConnect($connect)
        $watcherRunning = $client.Connected
      }
    } catch { $watcherRunning = $false } finally { $client.Dispose() }
  }
  [pscustomobject]@{ State = $state; Paused = $paused; CurrentId = $currentId; WatcherRunning = $watcherRunning }
}

function Set-StudioBusy([bool]$Busy, [string]$Message) {
  $StatusText.Text = $Message
  $ActivityDock.Visibility = if ($Busy) { 'Visible' } else { 'Collapsed' }
  $Window.Cursor = [Windows.Input.Cursors]::Arrow
  foreach ($control in @($CreateThemeButton,$HeroApplyButton,$PauseButton,$ResumeButton,$RuntimeVerifyButton,$RollbackButton,$RestoreButton)) {
    $control.IsEnabled = -not $Busy
  }
  if ($Busy) {
    $OperationTitle.Text = $Message
    $BusyBar.Value = 4
    $ProgressText.Text = ' · 4%'
    $ElapsedText.Text = '已用时 00:00'
    $CancelOperationButton.IsEnabled = $true
  }
}

function Invoke-StudioGuiCommand {
  param(
    [Parameter(Mandatory)][string[]]$Arguments,
    [Parameter(Mandatory)][string]$Label,
    [scriptblock]$OnSuccess,
    [int]$TimeoutSeconds = 120
  )
  if ($null -ne $script:ActiveOperation) {
    $StatusText.Text = '已有操作正在进行。'
    return $false
  }
  Set-StudioBusy $true $Label
  try {
    $tokens = @('-NoProfile','-ExecutionPolicy','RemoteSigned','-File',$StudioCli) + $Arguments + @('-Port',"$Port")
    $argumentLine = ($tokens | ForEach-Object { ConvertTo-DreamSkinProcessArgument -Value "$_" }) -join ' '
    $operationId = [guid]::NewGuid().ToString('N')
    $logRoot = Join-Path $StateRoot 'logs'
    New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
    $stdoutPath = Join-Path $logRoot "gui-$operationId.out.log"
    $stderrPath = Join-Path $logRoot "gui-$operationId.err.log"
    $process = Start-Process -FilePath $PowerShellExe -ArgumentList $argumentLine -PassThru -WindowStyle Hidden `
      -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
    $startedAt = [DateTime]::UtcNow
    $timer = [Windows.Threading.DispatcherTimer]::new()
    $timer.Interval = [TimeSpan]::FromMilliseconds(200)
    $operation = [pscustomobject]@{
      Id = $operationId; Process = $process; Timer = $timer; Label = $Label; StartedAt = $startedAt
      Cancelled = $false; StdoutPath = $stdoutPath; StderrPath = $stderrPath
      OnSuccess = $OnSuccess; TickHandler = $null
    }
    $script:ActiveOperation = $operation
    $tickHandler = {
      if ($null -eq $script:ActiveOperation -or $script:ActiveOperation.Id -cne $operationId) {
        $timer.Stop()
        return
      }
      $elapsed = ([DateTime]::UtcNow - $startedAt).TotalSeconds
      try {
        $process.Refresh()
        $hasExited = $process.HasExited
      } catch {
        $hasExited = $true
      }
      $progress = [Math]::Min(92, [Math]::Round(4 + ($elapsed * 10)))
      $BusyBar.Value = $progress
      $ProgressText.Text = " · $progress%"
      $ElapsedText.Text = '已用时 {0:mm\:ss}' -f [TimeSpan]::FromSeconds($elapsed)
      $timedOut = $elapsed -ge $TimeoutSeconds
      if (-not $hasExited -and -not $timedOut -and -not $operation.Cancelled) { return }

      $operationSucceeded = $false
      try {
        $timer.Stop()
        if (($timedOut -or $operation.Cancelled) -and -not $hasExited) {
          try { $process.Kill() } catch { }
          try { $process.WaitForExit(3000) | Out-Null } catch { }
        }
        try { $process.WaitForExit(3000) | Out-Null } catch { }
        $stdout = if (Test-Path -LiteralPath $stdoutPath) { Get-Content -Raw -LiteralPath $stdoutPath -ErrorAction SilentlyContinue } else { '' }
        $stderr = if (Test-Path -LiteralPath $stderrPath) { Get-Content -Raw -LiteralPath $stderrPath -ErrorAction SilentlyContinue } else { '' }
        if ($operation.Cancelled) { Set-StudioBusy $false '操作已取消'; return }
        if ($timedOut) { throw "$Label 超过 $TimeoutSeconds 秒，已安全停止。Codex 与主题状态保持可恢复。" }
        if ($process.ExitCode -ne 0) {
          $details = (($stderr + "`n" + $stdout).Trim())
          if ([string]::IsNullOrWhiteSpace($details)) { $details = "$Label 失败，退出代码 $($process.ExitCode)。" }
          throw $details
        }
        $BusyBar.Value = 100
        $ProgressText.Text = ' · 100%'
        Set-StudioBusy $false "$Label 完成"
        $operationSucceeded = $true
      } catch {
        $timer.Stop()
        Set-StudioBusy $false "$Label 失败"
        [void][Windows.MessageBox]::Show($_.Exception.Message, 'Codex Theme Studio', 'OK', 'Error')
      } finally {
        $callback = if ($operationSucceeded) { $operation.OnSuccess } else { $null }
        $script:ActiveOperation = $null
        try { if ($operation.TickHandler) { $timer.Remove_Tick($operation.TickHandler) } } catch { }
        try { if ($process.HasExited) { $process.Dispose() } } catch { }
        foreach ($path in @($stdoutPath,$stderrPath)) { try { if (Test-Path -LiteralPath $path) { [IO.File]::Delete($path) } } catch { } }
        if ($null -ne $callback) {
          try { & $callback } catch {
            $StatusText.Text = "$Label 已完成，界面刷新失败"
            [void][Windows.MessageBox]::Show("操作已经完成，但界面刷新失败。重新打开 Theme Studio 即可恢复显示。`n`n$($_.Exception.Message)", 'Codex Theme Studio', 'OK', 'Warning')
          }
        }
      }
    }.GetNewClosure()
    $operation.TickHandler = $tickHandler
    $timer.Add_Tick($tickHandler)
    $timer.Start()
    return $true
  } catch {
    $script:ActiveOperation = $null
    Set-StudioBusy $false "$Label 失败"
    [void][Windows.MessageBox]::Show($_.Exception.Message, 'Codex Theme Studio', 'OK', 'Error')
    return $false
  }
}

function Open-CodexThemeGenerator {
  try {
    $promptPath = Join-Path (Split-Path -Parent $PSScriptRoot) 'assets\create-theme-prompt.txt'
    if (-not (Test-Path -LiteralPath $promptPath -PathType Leaf)) { throw "Theme generator prompt is missing: $promptPath" }
    $prompt = (Get-Content -Raw -LiteralPath $promptPath -Encoding UTF8).Trim()
    if (-not $prompt.StartsWith('$codex-theme-generator ', [StringComparison]::Ordinal)) { throw 'Theme generator prompt is invalid.' }
    [Windows.Clipboard]::SetText($prompt)
    $codex = Get-DreamSkinCodexInstall
    [void](Start-DreamSkinCodex -Codex $codex)
    [void][Windows.MessageBox]::Show('已打开 Codex 并复制主题生成提示词。生成后先导入，再单独确认激活。','Codex Theme Studio','OK','Information')
  } catch { [void][Windows.MessageBox]::Show($_.Exception.Message, 'Codex Theme Studio', 'OK', 'Error') }
}

function Show-StudioPreview($Item) {
  if ($null -eq $Item) { return }
  $preview = [Windows.Window]::new()
  $preview.Title = "$($Item.Theme.name) · 预览"
  $preview.Width = 1040; $preview.Height = 660; $preview.WindowStartupLocation = 'CenterOwner'; $preview.Owner = $Window
  if ($null -ne $Window.Icon) { $preview.Icon = $Window.Icon }
  $preview.Background = [Windows.Media.BrushConverter]::new().ConvertFromString("$($Item.Theme.palette.canvas)")
  $grid = [Windows.Controls.Grid]::new()
  if ($Item.BackgroundPath) {
    $image = [Windows.Controls.Image]::new(); $image.Source = Get-StudioBitmap $Item.BackgroundPath
    $image.Stretch = 'UniformToFill'; $grid.Children.Add($image) | Out-Null
  }
  $panel = [Windows.Controls.Border]::new(); $panel.Width = 420; $panel.HorizontalAlignment = 'Left'; $panel.Margin = '38'; $panel.Padding = '28'; $panel.CornerRadius = '16'
  $panel.Background = [Windows.Media.BrushConverter]::new().ConvertFromString('#E6121418')
  $stack = [Windows.Controls.StackPanel]::new()
  foreach ($entry in @(@("$($Item.Theme.name)",30,'#FFF4DFC1'),@("$($Item.Theme.id)",12,'#FFB8B0A6'),@("$($Item.Theme.appearance) · $($Item.Theme.layout.mode)",14,'#FFE8D8C2'))) {
    $text = [Windows.Controls.TextBlock]::new(); $text.Text=$entry[0]; $text.FontSize=$entry[1]; $text.Foreground=[Windows.Media.BrushConverter]::new().ConvertFromString($entry[2]); $text.Margin='0,0,0,14'; $stack.Children.Add($text)|Out-Null
  }
  $panel.Child=$stack; $grid.Children.Add($panel)|Out-Null; $preview.Content=$grid; [void]$preview.ShowDialog()
}

function Set-HeroTheme($Item) {
  if ($null -eq $Item) { return }
  $script:SelectedItem = $Item
  $ui = Get-StudioUiState
  $HeroImage.Source = Get-StudioBitmap $Item.BackgroundPath
  $HeroName.Text = "$($Item.Theme.name)"
  $appearance = if ($Item.Theme.appearance -eq 'light') { '浅色' } else { '深色' }
  $layout = if ($Item.Theme.layout.mode -eq 'native') { '原生布局' } else { "$($Item.Theme.layout.mode) 布局" }
  $HeroMeta.Text = "$appearance · $layout · 已验证"
  $HeroDescription.Text = if ($Item.Theme.appearance -eq 'light') {
    '轻盈通透的视觉氛围，为阅读、整理与白天创作提供清晰舒适的工作空间。'
  } else {
    '深邃克制的暗色氛围，为长时间创作提供专注、舒适且沉浸的视觉体验。'
  }
  $isCurrent = $Item.Theme.id -ceq $ui.CurrentId -and -not $ui.Paused
  $HeroApplyButton.Content = if ($isCurrent) { '正在使用' } else { '应用主题' }
  $HeroApplyButton.IsEnabled = -not $isCurrent -and $null -eq $script:ActiveOperation
}

function New-ThemeCard($Item, [string]$CurrentId, [bool]$Paused) {
  $theme = $Item.Theme
  $selected = $script:SelectedItem -and $script:SelectedItem.Theme.id -ceq $theme.id
  $current = $theme.id -ceq $CurrentId -and -not $Paused
  $card = [Windows.Controls.Border]::new(); $card.Width=208; $card.Height=164; $card.Margin='0,0,14,0'; $card.CornerRadius='11'; $card.Cursor='Hand'; $card.Background=[Windows.Media.BrushConverter]::new().ConvertFromString('#111318')
  $card.BorderBrush=[Windows.Media.BrushConverter]::new().ConvertFromString($(if($selected){'#D6AE78'}else{'#34312E'})); $card.BorderThickness=$(if($selected){'2'}else{'1'})
  $layout=[Windows.Controls.Grid]::new(); $layout.RowDefinitions.Add([Windows.Controls.RowDefinition]::new())|Out-Null; $layout.RowDefinitions[0].Height='118'; $row=[Windows.Controls.RowDefinition]::new();$row.Height='*';$layout.RowDefinitions.Add($row)|Out-Null
  Add-StudioRoundedClip -Element $layout -Radius 10
  $visual=[Windows.Controls.Grid]::new(); $image=[Windows.Controls.Image]::new();$image.Source=Get-StudioBitmap $Item.BackgroundPath;$image.Stretch='UniformToFill';$visual.Children.Add($image)|Out-Null
  if($current){$badge=[Windows.Controls.Border]::new();$badge.Background=[Windows.Media.BrushConverter]::new().ConvertFromString('#E7C18D');$badge.CornerRadius='8';$badge.Padding='8,3';$badge.HorizontalAlignment='Right';$badge.VerticalAlignment='Top';$badge.Margin='8';$label=[Windows.Controls.TextBlock]::new();$label.Text='当前';$label.Foreground=[Windows.Media.BrushConverter]::new().ConvertFromString('#1A120A');$label.FontSize=10;$label.FontWeight='SemiBold';$badge.Child=$label;$visual.Children.Add($badge)|Out-Null}
  [Windows.Controls.Grid]::SetRow($visual,0);$layout.Children.Add($visual)|Out-Null
  $title=[Windows.Controls.TextBlock]::new();$title.Text="$($theme.name)";$title.FontSize=13;$title.FontWeight='SemiBold';$title.Foreground=[Windows.Media.BrushConverter]::new().ConvertFromString('#F0E1CE');$title.Margin='12,0';$title.VerticalAlignment='Center';$title.TextTrimming='CharacterEllipsis';[Windows.Controls.Grid]::SetRow($title,1);$layout.Children.Add($title)|Out-Null
  $card.Child=$layout;$card.Tag=$Item
  $card.Add_MouseEnter({param($sender,$eventArgs) if(-not ($script:SelectedItem -and $script:SelectedItem.Theme.id -ceq $sender.Tag.Theme.id)){$sender.BorderBrush=[Windows.Media.BrushConverter]::new().ConvertFromString('#6A5B49')}})
  $card.Add_MouseLeave({param($sender,$eventArgs) if(-not ($script:SelectedItem -and $script:SelectedItem.Theme.id -ceq $sender.Tag.Theme.id)){$sender.BorderBrush=[Windows.Media.BrushConverter]::new().ConvertFromString('#34312E')}})
  $card.Add_MouseLeftButtonUp({param($sender,$eventArgs) Set-HeroTheme $sender.Tag; Refresh-ThemeCards -PreserveOffset}.GetNewClosure())
  return $card
}

function Refresh-ThemeCards([switch]$PreserveOffset) {
  $offset = if ($PreserveOffset) { $ThemeScroll.HorizontalOffset } else { 0 }
  $ui=Get-StudioUiState; $query=$SearchBox.Text.Trim().ToLowerInvariant(); $ThemeStrip.Children.Clear()
  $visible=@($script:Themes | Where-Object {($script:Filter -eq 'all' -or $_.Theme.appearance -eq $script:Filter) -and (-not $query -or "$($_.Theme.name) $($_.Theme.id)".ToLowerInvariant().Contains($query))})
  if($visible.Count -and ($null -eq $script:SelectedItem -or $visible.Theme.id -notcontains $script:SelectedItem.Theme.id)){$script:SelectedItem=$visible[0]}
  if($script:SelectedItem){Set-HeroTheme $script:SelectedItem}
  foreach($item in $visible){$ThemeStrip.Children.Add((New-ThemeCard -Item $item -CurrentId $ui.CurrentId -Paused $ui.Paused))|Out-Null}
  $ThemeCountLabel.Text="· $($visible.Count) / $($script:Themes.Count)"
  foreach($pair in @(@($AllFilter,'all'),@($DarkFilter,'dark'),@($LightFilter,'light'))){
    $selected=$pair[1] -eq $script:Filter
    $pair[0].Background=[Windows.Media.BrushConverter]::new().ConvertFromString($(if($selected){'#2B241C'}else{'#17191D'}))
    $pair[0].BorderBrush=[Windows.Media.BrushConverter]::new().ConvertFromString($(if($selected){'#D6AE78'}else{'#3A3733'}))
    $pair[0].Foreground=[Windows.Media.BrushConverter]::new().ConvertFromString($(if($selected){'#F1D5AE'}else{'#EEE4D7'}))
  }
  if($PreserveOffset){$ThemeScroll.ScrollToHorizontalOffset($offset)}
}

function Refresh-StudioUi {
  $selectedId = if($script:SelectedItem){"$($script:SelectedItem.Theme.id)"}else{''}
  $script:Themes=@()
  foreach($saved in Get-DreamSkinSavedThemes -StateRoot $StateRoot -SkipImageMetadata){
    try{
      $loaded=Read-DreamSkinTheme -ThemeDirectory $saved.Path -SkipImageMetadata
      if($loaded.Theme.schemaVersion -eq 2){
        $bg=if($loaded.Theme.assets.homeBackground){[IO.Path]::GetFullPath((Join-Path $loaded.Directory "$($loaded.Theme.assets.homeBackground)"))}else{$null}
        if(-not $bg){
          $cover=Join-Path (Split-Path -Parent $PSScriptRoot) "assets\theme-covers\$($loaded.Theme.id).png"
          if(Test-Path -LiteralPath $cover -PathType Leaf){$bg=[IO.Path]::GetFullPath($cover)}
        }
        $script:Themes += [pscustomobject]@{Theme=$loaded.Theme;BackgroundPath=$bg;Directory=$loaded.Directory}
      }
    }catch{}
  }
  $ui=Get-StudioUiState
  $script:SelectedItem=$script:Themes|Where-Object{$_.Theme.id -ceq $selectedId}|Select-Object -First 1
  if(-not $script:SelectedItem){$script:SelectedItem=$script:Themes|Where-Object{$_.Theme.id -ceq $ui.CurrentId}|Select-Object -First 1}
  if(-not $script:SelectedItem){$script:SelectedItem=$script:Themes|Select-Object -First 1}
  $name=($script:Themes|Where-Object{$_.Theme.id -ceq $ui.CurrentId}|Select-Object -First 1).Theme.name
  $RuntimeLabel.Text=if($ui.WatcherRunning){'运行时正常'}else{'运行时未连接'}
  $RuntimeDot.Fill=[Windows.Media.BrushConverter]::new().ConvertFromString($(if($ui.WatcherRunning){'#50C989'}else{'#D8A757'}))
  $CurrentThemeValue.Text=if($name){$name}else{'官方外观'}
  $RuntimeModeValue.Text=if($ui.Paused){'已暂停'}elseif($ui.WatcherRunning){'主题运行中'}else{'未连接'}
  $ThemeStorePath.Text=$ThemePaths.Saved;$EnginePath.Text=(Split-Path -Parent $PSScriptRoot)
  Refresh-ThemeCards
}

function Show-StudioPage([string]$Page){
  $ThemesPage.Visibility=if($Page -eq 'themes'){'Visible'}else{'Collapsed'}
  $RuntimePage.Visibility=if($Page -eq 'runtime'){'Visible'}else{'Collapsed'}
  $SettingsPage.Visibility=if($Page -eq 'settings'){'Visible'}else{'Collapsed'}
  foreach($pair in @(@($ThemesNav,'themes'),@($RuntimeNav,'runtime'),@($SettingsNav,'settings'))){
    $active=$pair[1] -eq $Page
    $pair[0].Background=[Windows.Media.BrushConverter]::new().ConvertFromString($(if($active){'#181718'}else{'Transparent'}))
    $pair[0].BorderBrush=[Windows.Media.BrushConverter]::new().ConvertFromString($(if($active){'#D6AE78'}else{'Transparent'}))
    $pair[0].Foreground=[Windows.Media.BrushConverter]::new().ConvertFromString($(if($active){'#F1D5AE'}else{'#BDB5AB'}))
  }
}

$Window.Add_Closing({if($null -ne $script:ActiveOperation -and -not $script:ActiveOperation.Process.HasExited){try{$script:ActiveOperation.Process.Kill()}catch{}}})
$HeroContent.Add_SizeChanged({Update-HeroClip})
$Window.Add_Loaded({Update-HeroClip})
$TitleBar.Add_MouseLeftButtonDown({if($_.ClickCount -eq 2){if($Window.WindowState -eq 'Maximized'){$Window.WindowState='Normal'}else{$Window.WindowState='Maximized'}}else{$Window.DragMove()}})
$MinimizeButton.Add_Click({$Window.WindowState='Minimized'});$MaximizeButton.Add_Click({if($Window.WindowState -eq 'Maximized'){$Window.WindowState='Normal'}else{$Window.WindowState='Maximized'}});$CloseButton.Add_Click({$Window.Close()})
$ThemesNav.Add_Click({Show-StudioPage 'themes'});$RuntimeNav.Add_Click({Show-StudioPage 'runtime'});$SettingsNav.Add_Click({Show-StudioPage 'settings'})
$SearchBox.Add_TextChanged({$SearchHint.Visibility=if([string]::IsNullOrWhiteSpace($SearchBox.Text)){'Visible'}else{'Collapsed'};Refresh-ThemeCards})
foreach($pair in @(@($AllFilter,'all'),@($DarkFilter,'dark'),@($LightFilter,'light'))){$button=$pair[0];$button.Tag=$pair[1];$button.Add_Click({param($sender,$eventArgs)$script:Filter="$($sender.Tag)";Refresh-ThemeCards})}
$ScrollLeftButton.Add_Click({$ThemeScroll.ScrollToHorizontalOffset([Math]::Max(0,$ThemeScroll.HorizontalOffset-444))})
$ScrollRightButton.Add_Click({$ThemeScroll.ScrollToHorizontalOffset($ThemeScroll.HorizontalOffset+444)})
$CreateThemeButton.Add_Click({Open-CodexThemeGenerator})
$HeroPreviewButton.Add_Click({Show-StudioPreview $script:SelectedItem})
$HeroApplyButton.Add_Click({if($script:SelectedItem){$item=$script:SelectedItem;[void](Invoke-StudioGuiCommand -Arguments @('activate',"$($item.Theme.id)",'-RestartExisting') -Label "正在应用 $($item.Theme.name)" -OnSuccess {Refresh-StudioUi})}})
$CancelOperationButton.Add_Click({if($script:ActiveOperation){$script:ActiveOperation.Cancelled=$true;$OperationTitle.Text='正在取消操作';$CancelOperationButton.IsEnabled=$false;try{if(-not $script:ActiveOperation.Process.HasExited){$script:ActiveOperation.Process.Kill()}}catch{}}})
$RuntimeVerifyButton.Add_Click({[void](Invoke-StudioGuiCommand -Arguments @('verify') -Label '正在验证运行时' -OnSuccess {Refresh-StudioUi})})
$RollbackButton.Add_Click({[void](Invoke-StudioGuiCommand -Arguments @('rollback') -Label '正在回退主题' -OnSuccess {Refresh-StudioUi})})
$RestoreButton.Add_Click({[void](Invoke-StudioGuiCommand -Arguments @('restore') -Label '正在恢复官方外观' -OnSuccess {Refresh-StudioUi})})
$PauseButton.Add_Click({[void](Invoke-StudioGuiCommand -Arguments @('pause') -Label '正在暂停主题' -OnSuccess {Refresh-StudioUi})})
$ResumeButton.Add_Click({[void](Invoke-StudioGuiCommand -Arguments @('resume','-RestartExisting') -Label '正在重新应用主题' -OnSuccess {Refresh-StudioUi})})

Refresh-StudioUi
[void]$Window.ShowDialog()
