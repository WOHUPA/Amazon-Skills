[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string]$SourceRoot,
  [string]$StateRoot = (Join-Path $env:LOCALAPPDATA 'CodexThemeStudio')
)

$ErrorActionPreference = 'Stop'
$source = [System.IO.Path]::GetFullPath($SourceRoot)
$state = [System.IO.Path]::GetFullPath($StateRoot)
$common = Join-Path $source 'scripts\common-windows.ps1'
$themeWindows = Join-Path $source 'scripts\theme-windows.ps1'
if (-not (Test-Path -LiteralPath $common -PathType Leaf) -or
  -not (Test-Path -LiteralPath $themeWindows -PathType Leaf)) {
  throw "Theme Studio runtime bootstrap is incomplete: $source"
}

. $common
. $themeWindows
$engine = Install-DreamSkinRuntimeEngine -SkillRoot $source -StateRoot $state
$paths = Initialize-DreamSkinThemeStore -SkillRoot $engine.Root -StateRoot $state

[pscustomobject]@{
  status = 'COMPLETE'
  action = 'desktop-bootstrap'
  engine = $engine.Root
  themes = $paths.Saved
  version = (Get-Content -Raw -LiteralPath (Join-Path $engine.Root 'assets\studio-version.txt') -Encoding UTF8).Trim()
} | ConvertTo-Json -Compress
