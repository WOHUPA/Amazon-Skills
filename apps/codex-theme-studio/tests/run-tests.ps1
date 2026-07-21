[CmdletBinding()]
param([string]$Root)

$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($Root)) { $Root = Split-Path -Parent $PSScriptRoot }
$Root = [System.IO.Path]::GetFullPath($Root)
$Scripts = Join-Path $Root 'scripts'
. (Join-Path $Scripts 'common-windows.ps1')
. (Join-Path $Scripts 'theme-windows.ps1')

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
if ($guiSource -notmatch 'CreateThemeButton' -or $nativeClientSource -notmatch 'OpenThemeGenerator') {
  throw 'Theme Studio create-theme handoff is missing.'
}
if ($guiSource -notmatch 'HeroBackgroundButton' -or $guiSource -notmatch 'HeroDeleteButton' -or
    $nativeClientSource -notmatch 'ChooseLocalBackground' -or $nativeClientSource -notmatch 'DeleteSelectedTheme' -or
    $nativeEngineSource -notmatch 'SetBackground' -or $nativeEngineSource -notmatch 'DeleteTheme' -or
    $nativeEngineSource -notmatch 'deletedThemeIds') {
  throw 'Theme Studio local background or recoverable theme deletion flow is incomplete.'
}
if ($nativeClientSource -notmatch 'CancellationTokenSource' -or
    $nativeClientSource -notmatch 'ExecuteEngineAsync' -or
    $nativeClientSource -notmatch 'TimeSpan\.FromSeconds\(120\)' -or
    $nativeEngineSource -notmatch 'ReadToEndAsync' -or
    $nativeEngineSource -notmatch 'DateTime\.UtcNow\.Add\(timeout\)' -or
    $nativeEngineSource -notmatch 'WaitForExit\(120\)') {
  throw 'Theme Studio GUI commands must run asynchronously with timeout and operation guards.'
}
if ($guiSource -match '<Viewbox' -or
    $guiSource -notmatch '选择你的工作氛围' -or
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
$desktopSources = @(
  (Join-Path $Root 'desktop\Launcher.cs'),
  (Join-Path $Root 'desktop\Updater.cs'),
  (Join-Path $Root 'installer\CodexThemeStudio.iss'),
  (Join-Path $Root 'installer\CodexThemeStudio.wxs'),
  (Join-Path $Scripts 'build-windows-installer.ps1'),
  (Join-Path $Scripts 'desktop-bootstrap.ps1'),
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

$node = Get-DreamSkinNodeRuntime
& $node.Path '--check' (Join-Path $Scripts 'injector.mjs')
if ($LASTEXITCODE -ne 0) { throw 'injector.mjs syntax check failed.' }
& $node.Path '--check' (Join-Path $Root 'assets\renderer-inject.js')
if ($LASTEXITCODE -ne 0) { throw 'renderer-inject.js syntax check failed.' }
& $node.Path (Join-Path $Scripts 'injector.mjs') '--self-test'
if ($LASTEXITCODE -ne 0) { throw 'injector self-test failed.' }
$injectorSource = Get-Content -Raw -LiteralPath (Join-Path $Scripts 'injector.mjs')
if ($injectorSource -notmatch '--verify-removed' -or
    $injectorSource -notmatch 'expectsRemoved') {
  throw 'Official appearance verification mode is missing.'
}
$cliSource = Get-Content -Raw -LiteralPath (Join-Path $Scripts 'theme-studio.ps1')
if ($cliSource -notmatch 'ExpectRemoved:\$paused') {
  throw 'Theme Studio verify does not route paused state to official appearance verification.'
}
if ($cliSource -match "CreateShortcut\(\(Join-Path \$desktop 'Codex Theme Studio - Restore\.lnk'\)\)") {
  throw 'Theme Studio still creates the redundant desktop restore shortcut.'
}
foreach ($obsoleteName in @('Codex Dream Skin.lnk','Codex Dream Skin - Tray.lnk','Codex Dream Skin - Restore.lnk')) {
  if ($cliSource -notmatch [regex]::Escape($obsoleteName)) {
    throw "Theme Studio installer does not clean obsolete shortcut: $obsoleteName"
  }
}
if ($cliSource -notmatch 'shortcut\.IconLocation' -or
    $cliSource -notmatch 'SHChangeNotify') {
  throw 'Theme Studio installer does not assign the new shortcut icon and refresh the Windows Shell.'
}
if ($cliSource -notmatch 'CodexThemeStudio\.exe' -or $cliSource -match 'shortcut\.TargetPath = \$powershell') {
  throw 'Theme Studio shortcuts must open the native executable, never a PowerShell-hosted visual manager.'
}
foreach ($test in @('renderer-inject.test.mjs','visual-contract.test.mjs','host-adapter-fixture.test.mjs','injector-bootstrap.test.mjs','injector-one-shot.test.mjs','image-metadata.test.mjs')) {
  & $node.Path (Join-Path $PSScriptRoot $test)
  if ($LASTEXITCODE -ne 0) { throw "Node test failed: $test" }
}

$harnessRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("codex-theme-management-build-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $harnessRoot | Out-Null
try {
  $harnessExe = Join-Path $harnessRoot 'ThemeManagementHarness.exe'
  $csc = 'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe'
  & $csc '/nologo' '/target:exe' "/out:$harnessExe" `
    '/reference:System.dll' '/reference:System.Core.dll' '/reference:System.Drawing.dll' '/reference:System.Web.Extensions.dll' `
    (Join-Path $Root 'desktop\ThemeEngine.cs') (Join-Path $PSScriptRoot 'ThemeManagementHarness.cs')
  if ($LASTEXITCODE -ne 0) { throw 'Theme management harness compilation failed.' }
  & $harnessExe
  if ($LASTEXITCODE -ne 0) { throw 'Theme management harness failed.' }
} finally {
  $resolvedHarness = [System.IO.Path]::GetFullPath($harnessRoot)
  $tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()).TrimEnd('\') + '\'
  if (-not $resolvedHarness.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Refusing unsafe harness cleanup.' }
  [System.IO.Directory]::Delete($resolvedHarness, $true)
}

$pythonCommand = Get-Command python -ErrorAction Stop
$python = if ($pythonCommand.Path) { $pythonCommand.Path } else { $pythonCommand.Name }
foreach ($presetDirectory in Get-ChildItem -LiteralPath (Join-Path $Root 'presets') -Directory) {
  if (-not (Test-Path -LiteralPath (Join-Path $presetDirectory.FullName 'theme.json') -PathType Leaf)) { continue }
  $preset = $presetDirectory.Name
  & $python (Join-Path $Scripts 'validate_theme_v2.py') '--theme-dir' $presetDirectory.FullName
  if ($LASTEXITCODE -ne 0) { throw "Bundled Theme Pack v2 failed validation: $preset" }
}

$temporary = Join-Path ([System.IO.Path]::GetTempPath()) ("codex-theme-studio-test-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $temporary | Out-Null
try {
  $stateRoot = Join-Path $temporary 'state'
  $engine = Install-DreamSkinRuntimeEngine -SkillRoot $Root -StateRoot $stateRoot
  $paths = Initialize-DreamSkinThemeStore -SkillRoot $engine.Root -StateRoot $stateRoot
  $themes = @(Get-DreamSkinSavedThemes -StateRoot $stateRoot -SkipImageMetadata)
  $ids = @($themes.Id)
  foreach ($expected in @(
    'immersive-dark','clear-light','obsidian-gold',
    'doupo-cai-lin-heaven-python','doupo-medusa-green-lotus-evolution','doupo-nalan-dazzling-sunset',
    'doupo-qing-lin-triple-pupils','doupo-xiao-yan-flame-lotus','doupo-xiao-yixian-poison-world',
    'doupo-xun-er-emperor-seal','doupo-yun-yun-fallen-massacre','doupo-zi-yan-dragon-sword'
  )) {
    if ($ids -notcontains $expected) { throw "Theme store missing bundled preset: $expected" }
  }
  if ($ids.Count -ne 12) { throw "Expected 12 bundled Theme Pack v2 presets, got $($ids.Count)." }
  $initial = Read-DreamSkinTheme -ThemeDirectory $paths.Active
  if ($initial.Theme.id -cne 'immersive-dark' -or $initial.Theme.schemaVersion -ne 2) { throw 'Unexpected initial Theme Pack v2.' }
  $selected = $themes | Where-Object Id -CEQ 'clear-light'
  $active = Use-DreamSkinSavedTheme -ThemeDirectory $selected.Path -StateRoot $stateRoot
  if ($active.Theme.id -cne 'clear-light' -or $active.Theme.layout.mode -cne 'native') { throw 'Atomic v2 activation failed.' }

  $escape = Join-Path $temporary 'outside.svg'
  Set-Content -LiteralPath $escape -Value '<svg xmlns="http://www.w3.org/2000/svg" />' -Encoding utf8
  $themePath = Join-Path $paths.Active 'theme.json'
  $payload = Get-Content -Raw -LiteralPath $themePath | ConvertFrom-Json
  $payload.assets.icons.send = '..\outside.svg'
  $payload | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $themePath -Encoding utf8
  $rejected = $false
  try { $null = Read-DreamSkinTheme -ThemeDirectory $paths.Active } catch { $rejected = $true }
  if (-not $rejected) { throw 'Managed runtime accepted an escaping asset path.' }
} finally {
  $resolved = [System.IO.Path]::GetFullPath($temporary)
  $tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()).TrimEnd('\') + '\'
  if (-not $resolved.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Refusing unsafe test cleanup.' }
  [System.IO.Directory]::Delete($resolved, $true)
}

Write-Host 'PASS: Codex Theme Studio unit, schema, security, transaction, and runtime tests completed.'
