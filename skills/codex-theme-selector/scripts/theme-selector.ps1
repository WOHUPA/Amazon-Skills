[CmdletBinding()]
param(
  [ValidateSet('Status','List','Preview','Import','Activate','Rollback','Pause','Resume','Verify','Restore')]
  [string]$Action = 'List',
  [Alias('ThemePackRoot')]
  [string]$PackagePath,
  [string]$ThemeId,
  [string]$EngineRoot = (Join-Path $env:LOCALAPPDATA 'CodexThemeStudio\engine'),
  [string]$ClientPath = (Join-Path $env:LOCALAPPDATA 'Programs\Codex Theme Studio\CodexThemeStudio.exe'),
  [string]$ResultFile,
  [switch]$Confirm,
  [switch]$Full,
  [switch]$RestartExisting
)

$ErrorActionPreference = 'Stop'
$installed = Test-Path -LiteralPath $ClientPath -PathType Leaf
if (-not $installed) {
  [pscustomobject]@{
    status = if ($Action -eq 'Status') { 'COMPLETE' } else { 'BLOCKED' }
    runtimeStatus = 'NOT_INSTALLED'
    installed = $false
    engineRoot = $EngineRoot
    clientPath = $ClientPath
    error = if ($Action -eq 'Status') { $null } else { "Codex Theme Studio is not installed: $ClientPath" }
  } | ConvertTo-Json -Compress
  if ($Action -eq 'Status') { return }
  exit 2
}
$writeActions = @('Import','Stage','Activate','Rollback','Pause','Resume','Restore')
if ($Action -in $writeActions -and -not $Confirm) { throw "$Action requires -Confirm after explicit user intent." }

function Assert-ExactThemeId {
  param([string]$Value)
  if (-not $Value -or $Value -notmatch '^[a-z0-9]+(?:-[a-z0-9]+)*$') { throw "Invalid exact theme ID: $Value" }
}

$arguments = @('--engine', $Action.ToLowerInvariant())
if ($Action -eq 'Preview' -or $Action -eq 'Activate') {
  Assert-ExactThemeId $ThemeId
  $arguments += @('--theme', $ThemeId)
}
if ($Action -eq 'Import') {
  if (-not $PackagePath) { throw 'Import requires -PackagePath.' }
  $arguments += @('--package', [System.IO.Path]::GetFullPath($PackagePath))
}
if ($Confirm) { $arguments += '--confirm' }
$temporaryResult = -not $ResultFile
$resolvedResult = if ($ResultFile) {
  [System.IO.Path]::GetFullPath($ResultFile)
} else {
  Join-Path ([System.IO.Path]::GetTempPath()) ("codex-theme-result-" + [Guid]::NewGuid().ToString('N') + '.json')
}
$arguments += @('--result-file', $resolvedResult)
try {
  & $ClientPath @arguments
  $clientExitCode = $LASTEXITCODE
  if (Test-Path -LiteralPath $resolvedResult -PathType Leaf) {
    $envelope = Get-Content -Raw -LiteralPath $resolvedResult -Encoding UTF8 | ConvertFrom-Json
    if ($envelope.standardOutput) {
      $envelope.standardOutput
    } else {
      $envelope | ConvertTo-Json -Compress
    }
  }
  exit $clientExitCode
} finally {
  if ($temporaryResult -and (Test-Path -LiteralPath $resolvedResult -PathType Leaf)) {
    Remove-Item -LiteralPath $resolvedResult -Force
  }
}
