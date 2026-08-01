[CmdletBinding()]
param(
  [string]$Root,
  [switch]$MeasureIdleCpu
)

$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($Root)) { $Root = Split-Path -Parent $PSScriptRoot }
$Root = [System.IO.Path]::GetFullPath($Root)
$Scripts = Join-Path $Root 'scripts'

foreach ($file in Get-ChildItem -LiteralPath $Scripts -Filter '*.ps1' -File) {
  $tokens = $null
  $parseErrors = $null
  [System.Management.Automation.Language.Parser]::ParseFile($file.FullName, [ref]$tokens, [ref]$parseErrors) | Out-Null
  if ($parseErrors.Count) { throw "PowerShell parse failure in $($file.Name): $($parseErrors[0].Message)" }
}
$nativeLayout = Join-Path $Root 'assets\studio-window.xaml'
$nativeClient = Join-Path $Root 'desktop\StudioClient.cs'
$updateSourcePath = Join-Path $Root 'desktop\UpdateService.cs'
if (-not (Test-Path -LiteralPath $nativeLayout -PathType Leaf) -or -not (Test-Path -LiteralPath $nativeClient -PathType Leaf)) {
  throw 'Compiled Theme Studio client source or native WPF layout is missing.'
}
foreach ($removedScript in @('build_theme.py','migrate_legacy_theme.py')) {
  if (Test-Path -LiteralPath (Join-Path $Scripts $removedScript) -PathType Leaf) {
    throw "Independent Theme Studio still bundles generator-owned script: $removedScript"
  }
}
$createPrompt = Join-Path $Root 'assets\create-theme-prompt.txt'
if (-not (Test-Path -LiteralPath $createPrompt -PathType Leaf) -or
  -not (Get-Content -Raw -LiteralPath $createPrompt -Encoding UTF8).StartsWith('$codex-theme-generator ')) {
  throw 'Theme Studio create-theme prompt is missing or invalid.'
}
$createPromptSource = Get-Content -Raw -LiteralPath $createPrompt -Encoding UTF8
if ($createPromptSource -notmatch '背景质量优先' -or $createPromptSource -notmatch '本地参考') {
  throw 'Theme Studio create-theme prompt does not collect high-quality local background input.'
}
$lightCover = Join-Path $Root 'assets\theme-covers\clear-light.png'
if (-not (Test-Path -LiteralPath $lightCover -PathType Leaf) -or (Get-Item -LiteralPath $lightCover).Length -lt 100000) {
  throw 'Theme Studio light-theme editorial cover is missing or invalid.'
}
$guiSource = Get-Content -Raw -LiteralPath $nativeLayout
$nativeClientSource = Get-Content -Raw -LiteralPath $nativeClient
$updateSource = Get-Content -Raw -LiteralPath $updateSourcePath
$nativeEngineSource = Get-Content -Raw -LiteralPath (Join-Path $Root 'desktop\ThemeEngine.cs')
$recipeCompilerPath = Join-Path $Root 'desktop\RecipeThemeCompiler.cs'
$supervisorSource = Get-Content -Raw -LiteralPath (Join-Path $Root 'desktop\RuntimeSupervisor.cs')
$injectorPath = Join-Path $Scripts 'injector.mjs'
$rendererPath = Join-Path $Root 'assets\renderer-inject.js'
if ($guiSource -notmatch 'CreateThemeButton' -or $nativeClientSource -notmatch 'OpenThemeGenerator') {
  throw 'Theme Studio create-theme handoff is missing.'
}
if ($guiSource -notmatch 'RecipeThemeButton' -or $nativeClientSource -notmatch 'CompileRecipeTheme' -or
    $nativeClientSource -notmatch '不会应用主题') {
  throw 'Theme Recipe compilation UI must preserve the explicit activation boundary.'
}
if ($guiSource -notmatch 'SeriesStrip' -or $guiSource -notmatch 'ImportThemeButton' -or
    $guiSource -notmatch 'RuntimeSessionPanel' -or $guiSource -notmatch 'RuntimeActionsPanel') {
  throw 'Theme series, one-click import, or equal-height runtime panels are missing.'
}
Add-Type -AssemblyName PresentationFramework
Add-Type -AssemblyName System.Xaml
$layoutStream = [System.IO.File]::OpenRead($nativeLayout)
try { $layoutWindow = [System.Windows.Markup.XamlReader]::Load($layoutStream) } finally { $layoutStream.Dispose() }
$layoutWindow.FindName('ThemesPage').Visibility = 'Collapsed'
$layoutWindow.FindName('RuntimePage').Visibility = 'Visible'
$layoutWindow.Opacity = 0
$layoutWindow.ShowInTaskbar = $false
$layoutWindow.Show()
$layoutWindow.UpdateLayout()
$runtimeHeightDelta = [math]::Abs(
  $layoutWindow.FindName('RuntimeSessionPanel').ActualHeight -
  $layoutWindow.FindName('RuntimeActionsPanel').ActualHeight)
$layoutWindow.Close()
if ($runtimeHeightDelta -gt 1) { throw "Runtime panels differ by $runtimeHeightDelta px." }
if ($guiSource -notmatch 'HeroBackgroundButton' -or $guiSource -notmatch 'HeroDeleteButton' -or
    $nativeClientSource -notmatch 'ChooseLocalBackground' -or $nativeClientSource -notmatch 'DeleteSelectedTheme' -or
    $nativeEngineSource -notmatch 'SetBackground' -or $nativeEngineSource -notmatch 'DeleteTheme' -or
    $nativeEngineSource -notmatch 'deletedThemeIds') {
  throw 'Theme Studio local background or recoverable theme deletion flow is incomplete.'
}
if ($nativeClientSource -notmatch '系列名称（支持中文）' -or
    $nativeClientSource -match '系列 ID（小写字母、数字和连字符）' -or
    $nativeEngineSource -notmatch 'StandardOutputEncoding = new UTF8Encoding' -or
    $nativeEngineSource -notmatch 'StandardErrorEncoding = new UTF8Encoding') {
  throw 'Chinese series naming or UTF-8 child-process error handling is incomplete.'
}
if ($nativeClientSource -notmatch 'CancellationTokenSource' -or
    $nativeClientSource -notmatch 'ExecuteEngineAsync' -or
    $nativeClientSource -notmatch 'TimeSpan\.FromSeconds\(120\)' -or
    $nativeEngineSource -notmatch 'ReadToEndAsync' -or
    $nativeEngineSource -notmatch 'DateTime\.UtcNow\.Add\(timeout\)' -or
    $nativeEngineSource -notmatch 'WaitForExit\(120\)') {
  throw 'Theme Studio GUI commands must run asynchronously with timeout and operation guards.'
}
if (-not (Test-Path -LiteralPath $recipeCompilerPath -PathType Leaf) -or
    $nativeEngineSource -notmatch 'CreateRecipeTheme') {
  throw 'Theme Recipe v1 compilation bridge is missing.'
}
if ($guiSource -match '<Viewbox' -or
    $guiSource -notmatch '主题画廊' -or
    $guiSource -notmatch 'AI 生成主题' -or
    $guiSource -notmatch '自定义主题' -or
    $guiSource -notmatch '创作者中心' -or
    $guiSource -notmatch 'ActivityDock' -or
    $guiSource -notmatch 'CancelOperationButton' -or
    $guiSource -notmatch 'Width="1380" Height="840"') {
  throw 'Theme Studio premium editorial layout or non-blocking operation dock is missing.'
}
if ($guiSource -notmatch 'GlassFrameThickness="0"' -or
    $guiSource -match 'ResizeMode="CanResizeWithGrip"' -or
    $guiSource -notmatch 'HeroContent' -or
    $nativeClientSource -notmatch 'ApplyRoundedClip') {
  throw 'Theme Studio frameless window or closed hero-corner clipping is missing.'
}
if ($nativeClientSource -notmatch 'imageCache' -or
    $nativeClientSource -notmatch 'window\.Icon' -or
    $nativeClientSource -notmatch 'StudioTray') {
  throw 'Theme Studio operation lifetime, image cache, AppUserModelID, or window icon binding is missing.'
}
if ($supervisorSource -notmatch 'SELF_HEALING' -or
    $nativeEngineSource -notmatch 'codexProcesses\.Count > 0 && !allowRestart' -or
    $nativeEngineSource -notmatch 'NEEDS_RESTART') {
  throw 'RuntimeSupervisor safe-healing or explicit restart consent boundary is missing.'
}
$desktopSources = @(
  (Join-Path $Root 'desktop\Launcher.cs'),
  (Join-Path $Root 'desktop\Updater.cs'),
  (Join-Path $Root 'installer\CodexThemeStudio.iss'),
  (Join-Path $Root 'installer\CodexThemeStudio.wxs'),
  (Join-Path $Scripts 'build-windows-installer.ps1'),
  (Join-Path $Root 'assets\studio-version.txt')
)
foreach ($desktopSource in $desktopSources) {
  if (-not (Test-Path -LiteralPath $desktopSource -PathType Leaf)) {
    throw "Windows packaging source is missing: $desktopSource"
  }
}
$iconSource = Join-Path $Root 'assets\studio-icon.png'
$buildSource = Get-Content -Raw -LiteralPath (Join-Path $Scripts 'build-windows-installer.ps1')
if (-not (Test-Path -LiteralPath $iconSource -PathType Leaf) -or (Get-Item -LiteralPath $iconSource).Length -lt 100000) {
  throw 'Canonical Theme Studio icon source is missing or invalid.'
}
if ($nativeClientSource -notmatch 'StudioTray' -or $nativeClientSource -notmatch 'studio\.ico' -or
    $buildSource -notmatch 'studio-icon\.png' -or
    $buildSource -notmatch '@\(16,20,24,32,40,48,64,128,256\)') {
  throw 'Theme Studio launcher, taskbar, and tray do not share the multi-resolution icon pipeline.'
}
$launcherSource = Get-Content -Raw -LiteralPath (Join-Path $Root 'desktop\Launcher.cs')
if ($launcherSource -notmatch 'create-recipe') { throw 'Theme Recipe v1 CLI entrypoint is missing.' }
if ($launcherSource -notmatch 'CodexThemeStudio.Runtime.zip' -or $launcherSource -notmatch 'PrepareUninstall') {
  throw 'Windows launcher does not embed the runtime or expose uninstall preparation.'
}
if ($launcherSource -notmatch 'new StudioClient' -or
    $launcherSource -notmatch 'new StudioTray' -or
    $launcherSource -match 'StartRuntimeScript\("theme-studio-gui\.ps1"' -or
    $launcherSource -match 'StartRuntimeScript\("tray-dream-skin\.ps1"') {
  throw 'Windows launcher must host the compiled WPF window and tray without PowerShell UI processes.'
}
$installerSource = Get-Content -Raw -LiteralPath (Join-Path $Root 'installer\CodexThemeStudio.iss')
$wixInstallerSource = Get-Content -Raw -LiteralPath (Join-Path $Root 'installer\CodexThemeStudio.wxs')
$updaterSource = Get-Content -Raw -LiteralPath (Join-Path $Root 'desktop\Updater.cs')
if ($installerSource -notmatch 'CodexThemeStudio.Updater.exe' -or $installerSource -notmatch 'UninstallRun' -or
    $wixInstallerSource -notmatch 'MajorUpgrade' -or $wixInstallerSource -notmatch 'UpgradeCode' -or
    $updaterSource -notmatch 'msiexec.exe' -or $updaterSource -notmatch 'last-result.json') {
  throw 'Windows installer does not install the launcher or register uninstall cleanup.'
}
if ($installerSource -notmatch '\\.codextheme' -or $installerSource -notmatch '--background' -or
    $wixInstallerSource -notmatch '\\.codextheme' -or $launcherSource -notmatch 'SingleInstanceChannel') {
  throw 'Bundle file association, startup supervisor, or single-instance command channel is missing.'
}
if ($nativeClientSource -notmatch 'ThemePageSize = 18' -or
    $nativeClientSource -notmatch 'visible\.Skip\(themePageStart\)\.Take\(ThemePageSize\)' -or
    $launcherSource -notmatch '"status", "list", "preview", "import", "create-recipe", "activate", "rollback"' -or
    $launcherSource -match 'normalized == "delete"') {
  throw 'Theme list virtualization or the public native CLI boundary regressed.'
}
if ($nativeClientSource -notmatch 'post-success-refresh' -or
    $nativeClientSource -notmatch 'studio-client\.log' -or
    $nativeClientSource -notmatch '主题已经切换成功，但 Studio 刷新界面时遇到问题') {
  throw 'Theme operations can regress into false failure reports or lose native client diagnostics.'
}
$releaseWorkflow = Get-Content -Raw -LiteralPath (Join-Path $Root '.github\workflows\release.yml')
$manifestSource = Get-Content -Raw -LiteralPath (Join-Path $Scripts 'new-update-manifest.ps1')
$updatePublicKey = (Get-Content -Raw -LiteralPath (Join-Path $Root 'assets\update-public-key.txt')).Trim()
if ($updatePublicKey -notmatch '^RW[A-Za-z0-9+/=]{50,}$' -or
    $updateSource -notmatch 'VerifyMinisign' -or
    $updateSource -notmatch 'UpdateTrust\.PublicKeys' -or
    $updateSource -notmatch 'UpdaterSha256' -or
    $updateSource -notmatch 'DownloadWithRetry' -or
    $updateSource -match 'AuthenticodeVerifier|WinVerifyTrust' -or
    $buildSource -notmatch "minisignVersion = '0\.12'" -or
    $buildSource -notmatch '5535BE9E4E123831EBE6EF324AAFE9DDE507015C176191F9E20C3AD60567F9E1' -or
    $manifestSource -notmatch '-S -s \$signers\[\$index\]\.SecretKey' -or
    $releaseWorkflow -notmatch 'runs-on: windows-latest' -or
    $releaseWorkflow -notmatch 'MINISIGN_SECRET_KEY_BASE64' -or
    $buildSource -notmatch '15D50463C73DCE31FBEA5440AC33AF47E92D54D4188166D207E9E39577B8FE0F') {
  throw 'Certificate-free signed updater contract is incomplete.'
}

$nodeCommand = Get-Command node -ErrorAction Stop
$nodePath = if ($nodeCommand.Path) { $nodeCommand.Path } else { $nodeCommand.Name }
& $nodePath '--check' (Join-Path $Scripts 'injector.mjs')
if ($LASTEXITCODE -ne 0) { throw 'injector.mjs syntax check failed.' }
& $nodePath '--check' (Join-Path $Root 'assets\renderer-inject.js')
if ($LASTEXITCODE -ne 0) { throw 'renderer-inject.js syntax check failed.' }
& $nodePath (Join-Path $Scripts 'injector.mjs') '--self-test'
if ($LASTEXITCODE -ne 0) { throw 'injector self-test failed.' }
$injectorSource = Get-Content -Raw -LiteralPath (Join-Path $Scripts 'injector.mjs')
$rendererSource = Get-Content -Raw -LiteralPath $rendererPath
if ($injectorSource -notmatch '--verify-removed' -or
    $injectorSource -notmatch 'expectsRemoved') {
  throw 'Official appearance verification mode is missing.'
}
if ($injectorSource -notmatch 'Target\.targetCreated' -or
    $injectorSource -notmatch 'watchFiles' -or
    $injectorSource -match 'STRONG_THEME_AUDIT_MS' -or
    $rendererSource -match 'pointerover|pointerdown|pointerup' -or
    $rendererSource -match 'setInterval\(ensure,\s*5000\)') {
  throw 'Event-driven watcher or incremental renderer performance contract regressed.'
}
foreach ($obsoleteClient in @('theme-studio.ps1','theme-studio-gui.ps1','tray-dream-skin.ps1')) {
  if (Test-Path -LiteralPath (Join-Path $Scripts $obsoleteClient) -PathType Leaf) {
    throw "Obsolete PowerShell client remains in source: $obsoleteClient"
  }
}
foreach ($test in @('renderer-inject.test.mjs','visual-contract.test.mjs','host-adapter-fixture.test.mjs','injector-bootstrap.test.mjs','injector-one-shot.test.mjs','image-metadata.test.mjs')) {
  & $nodePath (Join-Path $PSScriptRoot $test)
  if ($LASTEXITCODE -ne 0) { throw "Node test failed: $test" }
}

$harnessRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("codex-theme-management-build-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $harnessRoot | Out-Null
try {
  $harnessExe = Join-Path $harnessRoot 'ThemeManagementHarness.exe'
  $csc = 'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe'
  & $csc '/nologo' '/target:exe' "/out:$harnessExe" `
    '/reference:System.dll' '/reference:System.Core.dll' '/reference:System.Drawing.dll' '/reference:System.Web.Extensions.dll' `
    '/reference:System.IO.Compression.dll' '/reference:System.IO.Compression.FileSystem.dll' `
    (Join-Path $Root 'desktop\ThemeEngine.cs') (Join-Path $Root 'desktop\RecipeThemeCompiler.cs') (Join-Path $Root 'desktop\AiThemeJobs.cs') (Join-Path $Root 'desktop\CodexAppServerClient.cs') (Join-Path $Root 'desktop\ThemeCatalog.cs') `
    (Join-Path $Root 'desktop\BundleManager.cs') (Join-Path $PSScriptRoot 'ThemeManagementHarness.cs')
  if ($LASTEXITCODE -ne 0) { throw 'Theme management harness compilation failed.' }
  & $harnessExe $Root
  if ($LASTEXITCODE -ne 0) { throw 'Theme management harness failed.' }
} finally {
  $resolvedHarness = [System.IO.Path]::GetFullPath($harnessRoot)
  $tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()).TrimEnd('\') + '\'
  if (-not $resolvedHarness.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Refusing unsafe harness cleanup.' }
  [System.IO.Directory]::Delete($resolvedHarness, $true)
}

$bundleHarnessRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("codex-theme-bundle-build-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $bundleHarnessRoot | Out-Null
try {
  $bundleHarnessExe = Join-Path $bundleHarnessRoot 'BundleCatalogHarness.exe'
  & $csc '/nologo' '/target:exe' "/out:$bundleHarnessExe" `
    '/reference:System.dll' '/reference:System.Core.dll' '/reference:System.Drawing.dll' '/reference:System.Web.Extensions.dll' `
    '/reference:System.IO.Compression.dll' '/reference:System.IO.Compression.FileSystem.dll' `
    (Join-Path $Root 'desktop\ThemeEngine.cs') (Join-Path $Root 'desktop\RecipeThemeCompiler.cs') (Join-Path $Root 'desktop\AiThemeJobs.cs') (Join-Path $Root 'desktop\CodexAppServerClient.cs') (Join-Path $Root 'desktop\ThemeCatalog.cs') `
    (Join-Path $Root 'desktop\BundleManager.cs') (Join-Path $PSScriptRoot 'BundleCatalogHarness.cs')
  if ($LASTEXITCODE -ne 0) { throw 'Bundle and Catalog harness compilation failed.' }
  & $bundleHarnessExe $Root
  if ($LASTEXITCODE -ne 0) { throw 'Bundle and Catalog harness failed.' }
} finally {
  $resolvedBundleHarness = [System.IO.Path]::GetFullPath($bundleHarnessRoot)
  $tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()).TrimEnd('\') + '\'
  if (-not $resolvedBundleHarness.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Refusing unsafe bundle harness cleanup.' }
  [System.IO.Directory]::Delete($resolvedBundleHarness, $true)
}

$supervisorHarnessRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("codex-theme-supervisor-build-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $supervisorHarnessRoot | Out-Null
try {
  $supervisorHarnessExe = Join-Path $supervisorHarnessRoot 'RuntimeSupervisorHarness.exe'
  & $csc '/nologo' '/target:exe' "/out:$supervisorHarnessExe" `
    '/reference:System.dll' '/reference:System.Core.dll' `
    (Join-Path $Root 'desktop\RuntimeSupervisor.cs') `
    (Join-Path $PSScriptRoot 'RuntimeSupervisorHarness.cs')
  if ($LASTEXITCODE -ne 0) { throw 'Runtime supervisor harness compilation failed.' }
  & $supervisorHarnessExe
  if ($LASTEXITCODE -ne 0) { throw 'Runtime supervisor recovery harness failed.' }
} finally {
  $resolvedSupervisorHarness = [System.IO.Path]::GetFullPath($supervisorHarnessRoot)
  $tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()).TrimEnd('\') + '\'
  if (-not $resolvedSupervisorHarness.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Refusing unsafe supervisor harness cleanup.' }
  [System.IO.Directory]::Delete($resolvedSupervisorHarness, $true)
}

$performanceHarnessRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("codex-theme-performance-build-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $performanceHarnessRoot | Out-Null
try {
  $performanceHarnessExe = Join-Path $performanceHarnessRoot 'StudioPerformanceHarness.exe'
  $presentationCore = (Get-ChildItem 'C:\Windows\Microsoft.NET\assembly\GAC_32\PresentationCore' -Recurse -Filter PresentationCore.dll -ErrorAction Stop | Select-Object -First 1).FullName
  $presentationFramework = (Get-ChildItem 'C:\Windows\Microsoft.NET\assembly\GAC_MSIL\PresentationFramework' -Recurse -Filter PresentationFramework.dll -ErrorAction Stop | Select-Object -First 1).FullName
  $windowsBase = (Get-ChildItem 'C:\Windows\Microsoft.NET\assembly\GAC_MSIL\WindowsBase' -Recurse -Filter WindowsBase.dll -ErrorAction Stop | Select-Object -First 1).FullName
  $systemXaml = (Get-ChildItem 'C:\Windows\Microsoft.NET\assembly\GAC_MSIL\System.Xaml' -Recurse -Filter System.Xaml.dll -ErrorAction Stop | Select-Object -First 1).FullName
  & $csc '/nologo' '/target:exe' "/out:$performanceHarnessExe" `
    '/reference:System.dll' '/reference:System.Core.dll' '/reference:System.Drawing.dll' '/reference:System.Web.Extensions.dll' `
    '/reference:System.IO.Compression.dll' '/reference:System.IO.Compression.FileSystem.dll' `
    "/reference:$systemXaml" "/reference:$windowsBase" "/reference:$presentationCore" `
    "/reference:$presentationFramework" '/reference:System.Windows.Forms.dll' `
    (Join-Path $Root 'desktop\StudioClient.cs') (Join-Path $Root 'desktop\ThemeEngine.cs') (Join-Path $Root 'desktop\RecipeThemeCompiler.cs') (Join-Path $Root 'desktop\AiThemeJobs.cs') (Join-Path $Root 'desktop\CodexAppServerClient.cs') `
    (Join-Path $Root 'desktop\ThemeCatalog.cs') (Join-Path $Root 'desktop\BundleManager.cs') `
    (Join-Path $Root 'desktop\RuntimeSupervisor.cs') (Join-Path $Root 'desktop\RuntimeAssetCache.cs') `
    (Join-Path $Root 'desktop\UpdateService.cs') (Join-Path $PSScriptRoot 'StudioPerformanceHarness.cs')
  if ($LASTEXITCODE -ne 0) { throw 'Studio performance harness compilation failed.' }
  if ($MeasureIdleCpu) { & $performanceHarnessExe $Root '--idle-120' }
  else { & $performanceHarnessExe $Root }
  if ($LASTEXITCODE -ne 0) { throw 'Studio 100-theme performance harness failed.' }
} finally {
  $resolvedPerformanceHarness = [System.IO.Path]::GetFullPath($performanceHarnessRoot)
  $tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()).TrimEnd('\') + '\'
  if (-not $resolvedPerformanceHarness.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Refusing unsafe performance harness cleanup.' }
  [System.IO.Directory]::Delete($resolvedPerformanceHarness, $true)
}

$pythonCommand = Get-Command python -ErrorAction Stop
$python = if ($pythonCommand.Path) { $pythonCommand.Path } else { $pythonCommand.Name }
foreach ($presetDirectory in Get-ChildItem -LiteralPath (Join-Path $Root 'presets') -Directory) {
  if (-not (Test-Path -LiteralPath (Join-Path $presetDirectory.FullName 'theme.json') -PathType Leaf)) { continue }
  $preset = $presetDirectory.Name
  & $python (Join-Path $Scripts 'validate_theme_v2.py') '--theme-dir' $presetDirectory.FullName
  if ($LASTEXITCODE -ne 0) { throw "Bundled Theme Pack v2 failed validation: $preset" }
}

Write-Host 'PASS: Codex Theme Studio unit, schema, security, transaction, and runtime tests completed.'
