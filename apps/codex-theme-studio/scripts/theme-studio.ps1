[CmdletBinding()]
param(
  [Parameter(Position = 0)][ValidateSet('list','preview','import','activate','rollback','pause','resume','verify','restore','install','update')]
  [string]$Command = 'list',
  [Parameter(Position = 1)][string]$Value,
  [int]$Port = 9335,
  [switch]$Full,
  [switch]$RestartExisting
)

$ErrorActionPreference = 'Stop'
$ToolRoot = Split-Path -Parent $PSScriptRoot
$StateRoot = Join-Path $env:LOCALAPPDATA 'CodexThemeStudio'
. (Join-Path $PSScriptRoot 'common-windows.ps1')
. (Join-Path $PSScriptRoot 'theme-windows.ps1')

function Write-StudioResult {
  param([string]$Status, [string]$Action, [hashtable]$Data = @{})
  $result = [ordered]@{ status = $Status; action = $Action; timestamp = (Get-Date).ToUniversalTime().ToString('o') }
  foreach ($entry in $Data.GetEnumerator()) { $result[$entry.Key] = $entry.Value }
  $result | ConvertTo-Json -Depth 10
}

function Get-StudioPython {
  foreach ($name in @('python.exe','python','py.exe','py')) {
    $command = Get-Command $name -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
  }
  throw 'Python 3 is required for Theme Pack v2 validation.'
}

function Test-StudioThemeV2 {
  param([Parameter(Mandatory = $true)][string]$ThemeDirectory)
  $python = Get-StudioPython
  $validator = Join-Path $PSScriptRoot 'validate_theme_v2.py'
  $output = @(& $python $validator '--theme-dir' $ThemeDirectory 2>&1)
  if ($LASTEXITCODE -ne 0) { throw "Theme Pack v2 validation failed:`n$($output -join "`n")" }
  return (($output -join "`n") | ConvertFrom-Json)
}

function Get-StudioPaths {
  $theme = Get-DreamSkinThemePaths -StateRoot $StateRoot
  $backups = Join-Path $StateRoot 'backups'
  $logs = Join-Path $StateRoot 'logs'
  foreach ($directory in @($theme.Root, $theme.Saved, $theme.Active, $backups, $logs)) {
    Ensure-DreamSkinManagedDirectory -Path $directory -Root $theme.Root
  }
  return [pscustomobject]@{ Theme = $theme; Backups = $backups; Logs = $logs }
}

function Get-StudioThemeById {
  param([Parameter(Mandatory = $true)][string]$Id)
  $matches = @(Get-DreamSkinSavedThemes -StateRoot $StateRoot -SkipImageMetadata | Where-Object { $_.Id -ceq $Id })
  if ($matches.Count -ne 1) { throw "Theme id must match exactly one installed theme: $Id" }
  return $matches[0]
}

function Copy-StudioDirectoryContents {
  param([string]$Source, [string]$Destination)
  New-Item -ItemType Directory -Force -Path $Destination | Out-Null
  Copy-Item -Path (Join-Path $Source '*') -Destination $Destination -Recurse -Force
}

function Save-StudioPreviousTheme {
  $paths = Get-StudioPaths
  $previous = Join-Path $paths.Backups 'previous-theme'
  if (Test-Path -LiteralPath $previous) { Remove-Item -LiteralPath $previous -Recurse -Force }
  Copy-StudioDirectoryContents -Source $paths.Theme.Active -Destination $previous
  $null = Read-DreamSkinTheme -ThemeDirectory $previous
  return $previous
}

function Invoke-StudioApply {
  $live = Get-DreamSkinLiveSessionContext -StateRoot $StateRoot
  if ($null -ne $live) {
    $paths = Get-StudioPaths
    Set-DreamSkinPaused -Paused $false -StateRoot $StateRoot | Out-Null
    $result = Invoke-DreamSkinNative -FilePath $live.NodePath -ArgumentList @(
      $live.Injector, '--once', '--port', "$($live.Port)", '--browser-id', $live.BrowserId,
      '--theme-dir', $paths.Theme.Active, '--pause-file', $paths.Theme.PauseFile,
      '--codex-version', "$($live.State.codexVersion)",
      '--timeout-ms', '30000'
    )
    if ($result.ExitCode -ne 0) {
      throw "Theme Studio live apply failed:`n$($result.Output -join "`n")"
    }
    return
  }
  $start = Join-Path $PSScriptRoot 'start-dream-skin.ps1'
  $arguments = @{ Port = $Port }
  if ($RestartExisting) { $arguments.RestartExisting = $true }
  else { $arguments.PromptRestart = $true }
  & $start @arguments
  if ($LASTEXITCODE -notin @(0, $null)) { throw "Theme Studio start failed with exit code $LASTEXITCODE" }
}

function Update-StudioStateThemeIds {
  param([string]$CurrentId, [string]$PreviousId)
  $statePath = Join-Path $StateRoot 'state.json'
  if (-not (Test-Path -LiteralPath $statePath -PathType Leaf)) { return }
  $state = Read-DreamSkinState -Path $statePath
  $state | Add-Member -NotePropertyName currentThemeId -NotePropertyValue $CurrentId -Force
  $state | Add-Member -NotePropertyName previousThemeId -NotePropertyValue $PreviousId -Force
  $state | Add-Member -NotePropertyName studioVersion -NotePropertyValue '2.4.1' -Force
  Write-DreamSkinState -Path $statePath -State $state
}

function Remove-StudioObsoleteShortcuts {
  param([Parameter(Mandatory)][string]$Desktop, [Parameter(Mandatory)][string]$StartMenu)
  $obsolete = @(
    (Join-Path $Desktop 'Codex Dream Skin.lnk'),
    (Join-Path $Desktop 'Codex Dream Skin - Tray.lnk'),
    (Join-Path $Desktop 'Codex Dream Skin - Restore.lnk'),
    (Join-Path $StartMenu 'Codex Dream Skin.lnk'),
    (Join-Path $StartMenu 'Codex Dream Skin - Tray.lnk'),
    (Join-Path $StartMenu 'Codex Dream Skin - Restore.lnk'),
    (Join-Path $Desktop 'Codex Theme Studio - Restore.lnk')
  )
  $removed = 0
  foreach ($shortcutPath in $obsolete) {
    if (Test-Path -LiteralPath $shortcutPath -PathType Leaf) {
      [System.IO.File]::Delete([System.IO.Path]::GetFullPath($shortcutPath))
      $removed += 1
    }
  }
  return $removed
}

function Send-StudioShellRefresh {
  if (-not ('CodexThemeStudioShellNotification' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class CodexThemeStudioShellNotification {
  [DllImport("shell32.dll")]
  public static extern void SHChangeNotify(uint eventId, uint flags, IntPtr item1, IntPtr item2);
}
'@
  }
  # SHCNE_ASSOCCHANGED refreshes removed ghost shortcuts and their cached icons without restarting Explorer.
  [CodexThemeStudioShellNotification]::SHChangeNotify(0x08000000, 0, [IntPtr]::Zero, [IntPtr]::Zero)
}

function Invoke-StudioInstall {
  $paths = Get-StudioPaths
  $engine = Install-DreamSkinRuntimeEngine -SkillRoot $ToolRoot -StateRoot $StateRoot
  $null = Initialize-DreamSkinThemeStore -SkillRoot $engine.Root -StateRoot $StateRoot
  $nativeClient = Join-Path $env:LOCALAPPDATA 'Programs\Codex Theme Studio\CodexThemeStudio.exe'
  $startMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
  $desktop = [Environment]::GetFolderPath('Desktop')
  $removedShortcuts = Remove-StudioObsoleteShortcuts -Desktop $desktop -StartMenu $startMenu
  $shortcutsCreated = $false
  if (Test-Path -LiteralPath $nativeClient -PathType Leaf) {
    $shell = New-Object -ComObject WScript.Shell
    foreach ($folder in @($desktop, $startMenu)) {
      $shortcut = $shell.CreateShortcut((Join-Path $folder 'Codex Theme Studio.lnk'))
      $shortcut.TargetPath = $nativeClient
      $shortcut.WorkingDirectory = Split-Path -Parent $nativeClient
      $shortcut.IconLocation = "$nativeClient,0"
      $shortcut.Description = 'Open the native Codex Theme Studio client'
      $shortcut.Save()
    }
    $shortcutsCreated = $true
    Send-StudioShellRefresh
  }
  Write-StudioResult -Status 'COMPLETE' -Action $Command -Data @{
    engine = $engine.Root; themes = $paths.Theme.Saved; client = $nativeClient
    shortcuts = $shortcutsCreated; removedShortcuts = $removedShortcuts
  }
}

switch ($Command) {
  'install' { Invoke-StudioInstall }
  'update' { Invoke-StudioInstall }
  'list' {
    $null = Get-StudioPaths
    $themes = @(Get-DreamSkinSavedThemes -StateRoot $StateRoot -SkipImageMetadata | ForEach-Object {
      $loaded = Read-DreamSkinTheme -ThemeDirectory $_.Path -SkipImageMetadata
      [ordered]@{ id = $_.Id; name = $_.Name; appearance = $loaded.Theme.appearance; layout = $loaded.Theme.layout.mode; path = $_.Path }
    })
    Write-StudioResult -Status 'COMPLETE' -Action 'list' -Data @{ themes = $themes }
  }
  'preview' {
    if (-not $Value) { throw 'preview requires an exact theme id.' }
    $theme = Get-StudioThemeById -Id $Value
    $preview = Join-Path $theme.Path 'preview.html'
    if (-not (Test-Path -LiteralPath $preview -PathType Leaf)) { throw "Theme preview is missing: $Value" }
    Write-StudioResult -Status 'COMPLETE' -Action 'preview' -Data @{ id = $Value; preview = $preview }
  }
  'import' {
    if (-not $Value) { throw 'import requires a Theme Pack directory.' }
    $source = [System.IO.Path]::GetFullPath($Value)
    $loaded = Read-DreamSkinTheme -ThemeDirectory $source
    if ($loaded.Theme.schemaVersion -ne 2) { throw 'Legacy themes must first be migrated with codex-skin-maker.' }
    $report = Test-StudioThemeV2 -ThemeDirectory $source
    $paths = Get-StudioPaths
    $destination = Join-Path $paths.Theme.Saved "$($loaded.Theme.id)"
    if (Test-Path -LiteralPath $destination) { throw "Refusing to overwrite installed theme id: $($loaded.Theme.id)" }
    $staging = Join-Path $paths.Theme.Root ".import-$([guid]::NewGuid().ToString('N'))"
    try {
      Copy-StudioDirectoryContents -Source $source -Destination $staging
      $null = Test-StudioThemeV2 -ThemeDirectory $staging
      Move-Item -LiteralPath $staging -Destination $destination
    } finally {
      if (Test-Path -LiteralPath $staging) { Remove-Item -LiteralPath $staging -Recurse -Force }
    }
    Write-StudioResult -Status 'COMPLETE' -Action 'import' -Data @{ id = "$($loaded.Theme.id)"; path = $destination; validation = $report.status }
  }
  'activate' {
    if (-not $Value) { throw 'activate requires an exact theme id.' }
    $selected = Get-StudioThemeById -Id $Value
    $paths = Get-StudioPaths
    $current = Read-DreamSkinTheme -ThemeDirectory $paths.Theme.Active
    $previousId = "$($current.Theme.id)"
    $previous = Save-StudioPreviousTheme
    try {
      $null = Use-DreamSkinSavedTheme -ThemeDirectory $selected.Path -StateRoot $StateRoot
      Invoke-StudioApply
      Update-StudioStateThemeIds -CurrentId $Value -PreviousId $previousId
    } catch {
      $failure = $_
      Get-ChildItem -LiteralPath $paths.Theme.Active -Force | Remove-Item -Recurse -Force
      Copy-StudioDirectoryContents -Source $previous -Destination $paths.Theme.Active
      try { Invoke-StudioApply } catch {}
      throw $failure
    }
    Write-StudioResult -Status 'COMPLETE' -Action 'activate' -Data @{ currentTheme = $Value; previousTheme = $previousId }
  }
  'rollback' {
    $paths = Get-StudioPaths
    $previous = Join-Path $paths.Backups 'previous-theme'
    if (-not (Test-Path -LiteralPath (Join-Path $previous 'theme.json') -PathType Leaf)) { throw 'No previous theme backup is available.' }
    $current = Read-DreamSkinTheme -ThemeDirectory $paths.Theme.Active
    $target = Read-DreamSkinTheme -ThemeDirectory $previous
    $swap = Join-Path $paths.Backups ".rollback-$([guid]::NewGuid().ToString('N'))"
    Copy-StudioDirectoryContents -Source $paths.Theme.Active -Destination $swap
    try {
      Get-ChildItem -LiteralPath $paths.Theme.Active -Force | Remove-Item -Recurse -Force
      Copy-StudioDirectoryContents -Source $previous -Destination $paths.Theme.Active
      Invoke-StudioApply
      Remove-Item -LiteralPath $previous -Recurse -Force
      Move-Item -LiteralPath $swap -Destination $previous
      Update-StudioStateThemeIds -CurrentId "$($target.Theme.id)" -PreviousId "$($current.Theme.id)"
    } catch {
      Get-ChildItem -LiteralPath $paths.Theme.Active -Force | Remove-Item -Recurse -Force
      Copy-StudioDirectoryContents -Source $swap -Destination $paths.Theme.Active
      throw
    } finally {
      if (Test-Path -LiteralPath $swap) { Remove-Item -LiteralPath $swap -Recurse -Force }
    }
    Write-StudioResult -Status 'COMPLETE' -Action 'rollback' -Data @{ currentTheme = "$($target.Theme.id)"; previousTheme = "$($current.Theme.id)" }
  }
  'pause' {
    $null = Set-DreamSkinPaused -Paused $true -StateRoot $StateRoot
    $result = Invoke-DreamSkinLiveRemove -StateRoot $StateRoot
    Write-StudioResult -Status $(if ($result.Removed -or -not $result.Attempted) { 'COMPLETE' } else { 'PARTIAL' }) -Action 'pause' -Data @{ removed = $result.Removed; message = $result.Message }
  }
  'resume' {
    $null = Set-DreamSkinPaused -Paused $false -StateRoot $StateRoot
    Invoke-StudioApply
    Write-StudioResult -Status 'COMPLETE' -Action 'resume'
  }
  'verify' {
    $verify = Join-Path $PSScriptRoot 'verify-dream-skin.ps1'
    $paused = Test-DreamSkinPaused -StateRoot $StateRoot
    & $verify -Port $Port -ExpectRemoved:$paused
    if ($LASTEXITCODE -notin @(0, $null)) { throw "Verification failed with exit code $LASTEXITCODE" }
    if ($paused) {
      Write-StudioResult -Status 'COMPLETE' -Action 'verify' -Data @{ officialAppearance = $true; paused = $true }
    }
  }
  'restore' {
    if ($Full) {
      & (Join-Path $PSScriptRoot 'restore-dream-skin.ps1') -Port $Port -RestoreBaseTheme -PromptRestart
    } else {
      $null = Set-DreamSkinPaused -Paused $true -StateRoot $StateRoot
      $result = Invoke-DreamSkinLiveRemove -StateRoot $StateRoot
      if ($result.Attempted -and -not $result.Removed) { throw $result.Message }
      Write-StudioResult -Status 'COMPLETE' -Action 'restore' -Data @{ officialAppearance = $true; runtimePreserved = $true }
    }
  }
}
