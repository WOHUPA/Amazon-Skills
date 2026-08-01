[CmdletBinding()]
param(
  [string]$AppVersion = '2.7.5',
  [string]$InstallerPath,
  [string]$ManifestPath
)

$ErrorActionPreference = 'Stop'
$root = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
if (-not $InstallerPath) { $InstallerPath = Join-Path $root "dist\Codex-Theme-Studio-$AppVersion-Windows-x64.msi" }
if (-not $ManifestPath) { $ManifestPath = Join-Path $root 'dist\latest.json' }
$installer = [System.IO.Path]::GetFullPath($InstallerPath)
$manifestFile = [System.IO.Path]::GetFullPath($ManifestPath)
$signatureFile = "$installer.minisig"
foreach ($required in @($installer, $manifestFile, $signatureFile)) {
  if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw "Update verification input is missing: $required" }
}

$manifest = Get-Content -Raw -LiteralPath $manifestFile -Encoding UTF8 | ConvertFrom-Json
$package = $manifest.platforms.'windows-x86_64-msi'
$actualHash = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash
if ($manifest.version -cne $AppVersion -or $package.sha256 -ine $actualHash) {
  throw 'Update manifest version or SHA-256 does not match the installer.'
}
$signatureText = [System.IO.File]::ReadAllText($signatureFile, [System.Text.Encoding]::UTF8)
if ($package.signature.Replace("`r`n", "`n") -cne $signatureText.Replace("`r`n", "`n")) {
  throw 'Update manifest signature does not match the published .minisig file.'
}

$csc = 'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$harnessSource = Join-Path $root 'tests\UpdateVerifierHarness.cs'
$updateSource = Join-Path $root 'desktop\UpdateService.cs'
$trustSource = Join-Path $root 'build\windows\UpdateTrust.g.cs'
$engineRoot = Join-Path $root 'build\windows\runtime'
$testRoot = Join-Path $root 'build\windows\tests'
New-Item -ItemType Directory -Path $testRoot -Force | Out-Null
$harness = Join-Path $testRoot 'UpdateVerifierHarness.exe'

& $csc /nologo /target:exe /optimize+ "/out:$harness" /reference:System.dll /reference:System.Core.dll /reference:System.Web.Extensions.dll $updateSource $trustSource $harnessSource
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $harness -PathType Leaf)) { throw 'Update verifier harness compilation failed.' }
& $harness $engineRoot $installer $signatureFile
if ($LASTEXITCODE -ne 0) { throw 'Update verifier integration test failed.' }

[pscustomobject]@{
  status = 'COMPLETE'
  version = $AppVersion
  installer = $installer
  sha256 = $actualHash
  authenticode = "$( (Get-AuthenticodeSignature -LiteralPath $installer).Status )"
  validSignatureAccepted = $true
  tamperedInstallerRejected = $true
} | ConvertTo-Json
