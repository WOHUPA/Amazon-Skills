[CmdletBinding()]
param(
  [ValidateRange(1024, 65535)][int]$Port = 9335
)

$ErrorActionPreference = 'Stop'

# NOTE: 首次启用必须在 Codex 完全退出后执行，避免安装器修改配置时与运行进程竞争。
$presetRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$windowsRoot = [System.IO.Path]::GetFullPath((Join-Path $presetRoot '..\..'))
$scriptsRoot = Join-Path $windowsRoot 'scripts'
$installer = Join-Path $scriptsRoot 'install-dream-skin.ps1'
$stateRoot = [System.IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'CodexThemeStudio'))
$screenshotPath = Join-Path $stateRoot 'xiao-yan-verify.png'

. (Join-Path $scriptsRoot 'common-windows.ps1')
. (Join-Path $scriptsRoot 'theme-windows.ps1')

$codex = Get-DreamSkinCodexInstall
if ((Get-DreamSkinCodexProcesses -Codex $codex).Count -gt 0) {
  throw '请先完全退出 Codex，再重新运行本脚本；脚本不会自动终止正在运行的 Codex。'
}

$sourceTheme = Read-DreamSkinTheme -ThemeDirectory $presetRoot
if ($sourceTheme.Theme.id -ne 'preset-xiao-yan') {
  throw '萧炎主题 ID 校验失败，拒绝安装。'
}

$paths = Get-DreamSkinThemePaths -StateRoot $stateRoot
Ensure-DreamSkinManagedDirectory -Path $paths.Root -Root $paths.Root
Ensure-DreamSkinManagedDirectory -Path $paths.Saved -Root $paths.Root
$savedThemeRoot = Join-Path $paths.Saved 'preset-xiao-yan'

if (-not (Test-Path -LiteralPath $savedThemeRoot -PathType Container)) {
  Ensure-DreamSkinManagedDirectory -Path $savedThemeRoot -Root $paths.Root
  Copy-Item -LiteralPath $sourceTheme.ImagePath -Destination (Join-Path $savedThemeRoot 'background.jpg')
  Copy-Item -LiteralPath $sourceTheme.ThemePath -Destination (Join-Path $savedThemeRoot 'theme.json')
}

$savedTheme = Read-DreamSkinTheme -ThemeDirectory $savedThemeRoot
$sourceHash = (Get-FileHash -LiteralPath $sourceTheme.ImagePath -Algorithm SHA256).Hash
$savedHash = (Get-FileHash -LiteralPath $savedTheme.ImagePath -Algorithm SHA256).Hash
if ($savedTheme.Theme.id -ne 'preset-xiao-yan' -or $savedHash -ne $sourceHash) {
  throw '本机已存在不同内容的同名萧炎主题，拒绝静默覆盖。'
}

$engineStart = Join-Path $stateRoot 'engine\scripts\start-dream-skin.ps1'
if (-not (Test-Path -LiteralPath $engineStart -PathType Leaf)) {
  & $installer -Port $Port
}
if (-not (Test-Path -LiteralPath $engineStart -PathType Leaf)) {
  throw 'Dream Skin 运行时安装后未找到启动脚本。'
}

# 用户主动运行本脚本即确认启用已预览的 preset-xiao-yan；官方外观仍可由恢复快捷方式还原。
$null = Use-DreamSkinSavedTheme -ThemeDirectory $savedThemeRoot -StateRoot $stateRoot
& $engineStart -Port $Port

$verifyScript = Join-Path $stateRoot 'engine\scripts\verify-dream-skin.ps1'
$powershell = (Get-Command powershell.exe -ErrorAction Stop).Source
& $powershell -NoProfile -ExecutionPolicy RemoteSigned -File $verifyScript `
  -Port $Port -ScreenshotPath $screenshotPath
if ($LASTEXITCODE -ne 0) {
  throw 'Dream Skin 已启动，但实机验证失败；请查看本机 CodexThemeStudio 日志。'
}

[pscustomobject]@{
  status = 'COMPLETE'
  themeId = 'preset-xiao-yan'
  stateRoot = $stateRoot
  port = $Port
  screenshot = $screenshotPath
} | ConvertTo-Json -Depth 3
