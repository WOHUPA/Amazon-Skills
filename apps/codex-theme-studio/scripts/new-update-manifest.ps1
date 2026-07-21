[CmdletBinding()]
param(
  [Parameter(Mandatory)][string]$Version,
  [Parameter(Mandatory)][string]$Repository,
  [Parameter(Mandatory)][string]$InstallerPath,
  [Parameter(Mandatory)][string[]]$SecretKeyPath,
  [string]$BridgeInstallerPath,
  [string]$ReleaseTagPrefix = 'v',
  [string]$PublicKeysPath,
  [string]$MinisignPath,
  [string]$Notes = '',
  [string]$OutputPath
)

$ErrorActionPreference = 'Stop'
$root = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$installer = [System.IO.Path]::GetFullPath($InstallerPath)
if (-not (Test-Path -LiteralPath $installer -PathType Leaf) -or -not $installer.EndsWith('.msi', [StringComparison]::OrdinalIgnoreCase)) {
  throw "Primary MSI installer does not exist: $installer"
}
$bridgeInstaller = if ($BridgeInstallerPath) { [System.IO.Path]::GetFullPath($BridgeInstallerPath) } else { $null }
if ($bridgeInstaller -and (-not (Test-Path -LiteralPath $bridgeInstaller -PathType Leaf) -or
    -not $bridgeInstaller.EndsWith('.exe', [StringComparison]::OrdinalIgnoreCase))) {
  throw "Bridge EXE installer does not exist: $bridgeInstaller"
}
if (-not $PublicKeysPath) { $PublicKeysPath = Join-Path $root 'assets\update-public-keys.txt' }
$publicKeysFile = [System.IO.Path]::GetFullPath($PublicKeysPath)
if (-not (Test-Path -LiteralPath $publicKeysFile -PathType Leaf)) { throw 'Minisign public key ring does not exist.' }
if (-not $MinisignPath) { $MinisignPath = Join-Path $root 'build\windows\runtime\runtime\minisign.exe' }
$minisign = [System.IO.Path]::GetFullPath($MinisignPath)
if (-not (Test-Path -LiteralPath $minisign -PathType Leaf)) { throw 'Bundled Minisign executable does not exist.' }
if ($Repository -cnotmatch '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$') { throw 'Repository must use owner/name format.' }
if ($ReleaseTagPrefix -cnotmatch '^[A-Za-z0-9_.-]*$') { throw 'ReleaseTagPrefix contains unsupported characters.' }
$cleanVersion = $Version.TrimStart('v','V')
if ($cleanVersion -cnotmatch '^\d+\.\d+\.\d+(?:\.\d+)?$') { throw 'Version must be numeric semver.' }
$publicKeys = @(Get-Content -LiteralPath $publicKeysFile -Encoding UTF8 | ForEach-Object { $_.Trim() } | Where-Object { $_ -and -not $_.StartsWith('#') })
if ($publicKeys.Count -eq 0) { throw 'Minisign public key ring is empty.' }
foreach ($publicKey in $publicKeys) {
  if ($publicKey -cnotmatch '^RW[A-Za-z0-9+/=]{50,}$') { throw "Minisign public key is invalid: $publicKey" }
}

$signers = @()
foreach ($keyPath in $SecretKeyPath) {
  $secretKey = [System.IO.Path]::GetFullPath($keyPath)
  if (-not (Test-Path -LiteralPath $secretKey -PathType Leaf)) { throw 'Minisign secret key does not exist.' }
  $derivedPublic = Join-Path ([System.IO.Path]::GetTempPath()) ("codex-theme-studio-" + [guid]::NewGuid().ToString('N') + '.pub')
  try {
    & $minisign -R -s $secretKey -p $derivedPublic
    if ($LASTEXITCODE -ne 0) { throw 'Unable to derive the Minisign public key from a release secret.' }
    $derivedKey = [string](Get-Content -LiteralPath $derivedPublic -Encoding UTF8 | Where-Object { $_ -match '^RW[A-Za-z0-9+/=]+$' } | Select-Object -First 1)
    if ($publicKeys -cnotcontains $derivedKey) { throw 'A release secret key is not present in assets/update-public-keys.txt.' }
    $signers += [pscustomobject]@{ SecretKey = $secretKey; PublicKey = $derivedKey }
  } finally {
    if (Test-Path -LiteralPath $derivedPublic) { [System.IO.File]::Delete($derivedPublic) }
  }
}
if ($signers.Count -eq 0) { throw 'At least one Minisign release key is required.' }

function New-SignedPackage([string]$Path, [string]$Platform) {
  $signatures = @()
  for ($index = 0; $index -lt $signers.Count; $index++) {
    $signaturePath = if ($index -eq 0) { "$Path.minisig" } else { "$Path.key$index.minisig" }
    if (Test-Path -LiteralPath $signaturePath) { [System.IO.File]::Delete($signaturePath) }
    & $minisign -S -s $signers[$index].SecretKey -m $Path -x $signaturePath -t "Codex Theme Studio $cleanVersion"
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $signaturePath -PathType Leaf)) { throw "Minisign update signing failed: $Path" }
    & $minisign -V -q -m $Path -x $signaturePath -P $signers[$index].PublicKey
    if ($LASTEXITCODE -ne 0) { throw "Generated Minisign update signature failed verification: $Path" }
    $signatures += [System.IO.File]::ReadAllText($signaturePath, [System.Text.Encoding]::UTF8)
  }
  $fileName = [System.IO.Path]::GetFileName($Path)
  return [ordered]@{
    signature = $signatures[0]
    signatures = $signatures
    sha256 = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
    url = "https://github.com/$Repository/releases/download/$ReleaseTagPrefix$cleanVersion/$fileName"
    installer = $Platform
  }
}

$platforms = [ordered]@{
  'windows-x86_64-msi' = New-SignedPackage -Path $installer -Platform 'msi'
}
if ($bridgeInstaller) {
  $platforms['windows-x86_64'] = New-SignedPackage -Path $bridgeInstaller -Platform 'exe-bridge'
}
$manifest = [ordered]@{
  version = $cleanVersion
  notes = if ($Notes) { $Notes } else { "Codex Theme Studio $cleanVersion" }
  pub_date = [DateTime]::UtcNow.ToString('o')
  platforms = $platforms
}
if (-not $OutputPath) { $OutputPath = Join-Path (Split-Path -Parent $installer) 'latest.json' }
$output = [System.IO.Path]::GetFullPath($OutputPath)
[System.IO.Directory]::CreateDirectory((Split-Path -Parent $output)) | Out-Null
[System.IO.File]::WriteAllText($output, ($manifest | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))
[pscustomobject]@{
  status = 'COMPLETE'
  manifest = $output
  version = $cleanVersion
  installer = $installer
  bridgeInstaller = $bridgeInstaller
  signerCount = $signers.Count
  authenticode = "$( (Get-AuthenticodeSignature -LiteralPath $installer).Status )"
} | ConvertTo-Json
