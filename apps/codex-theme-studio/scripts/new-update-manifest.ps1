[CmdletBinding()]
param(
  [Parameter(Mandatory)][string]$Version,
  [Parameter(Mandatory)][string]$Repository,
  [Parameter(Mandatory)][string]$InstallerPath,
  [Parameter(Mandatory)][string]$SecretKeyPath,
  [string]$ReleaseTagPrefix = 'v',
  [string]$PublicKeyPath,
  [string]$MinisignPath,
  [string]$Notes = '',
  [string]$OutputPath
)

$ErrorActionPreference = 'Stop'
$root = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$installer = [System.IO.Path]::GetFullPath($InstallerPath)
if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) { throw "Installer does not exist: $installer" }
$secretKey = [System.IO.Path]::GetFullPath($SecretKeyPath)
if (-not (Test-Path -LiteralPath $secretKey -PathType Leaf)) { throw 'Minisign secret key does not exist.' }
if (-not $PublicKeyPath) { $PublicKeyPath = Join-Path $root 'assets\update-public-key.txt' }
$publicKeyFile = [System.IO.Path]::GetFullPath($PublicKeyPath)
if (-not (Test-Path -LiteralPath $publicKeyFile -PathType Leaf)) { throw 'Minisign public key does not exist.' }
if (-not $MinisignPath) { $MinisignPath = Join-Path $root 'build\windows\runtime\runtime\minisign.exe' }
$minisign = [System.IO.Path]::GetFullPath($MinisignPath)
if (-not (Test-Path -LiteralPath $minisign -PathType Leaf)) { throw 'Bundled Minisign executable does not exist.' }
if ($Repository -cnotmatch '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$') { throw 'Repository must use owner/name format.' }
if ($ReleaseTagPrefix -cnotmatch '^[A-Za-z0-9_.-]*$') { throw 'ReleaseTagPrefix contains unsupported characters.' }
$cleanVersion = $Version.TrimStart('v','V')
if ($cleanVersion -cnotmatch '^\d+\.\d+\.\d+(?:\.\d+)?$') { throw 'Version must be numeric semver.' }
$publicKey = [System.IO.File]::ReadAllText($publicKeyFile, [System.Text.Encoding]::UTF8).Trim()
if ($publicKey -cnotmatch '^RW[A-Za-z0-9+/=]{50,}$') { throw 'Minisign public key is invalid.' }

$derivedPublic = Join-Path ([System.IO.Path]::GetTempPath()) ("codex-theme-studio-" + [guid]::NewGuid().ToString('N') + '.pub')
try {
  & $minisign -R -s $secretKey -p $derivedPublic
  if ($LASTEXITCODE -ne 0) { throw 'Unable to derive the Minisign public key from the release secret.' }
  $derivedKey = [string](Get-Content -LiteralPath $derivedPublic -Encoding UTF8 | Where-Object { $_ -match '^RW[A-Za-z0-9+/=]+$' } | Select-Object -First 1)
  if ($derivedKey -cne $publicKey) { throw 'Release secret key does not match assets/update-public-key.txt.' }
} finally {
  if (Test-Path -LiteralPath $derivedPublic) { [System.IO.File]::Delete($derivedPublic) }
}

$signaturePath = "$installer.minisig"
if (Test-Path -LiteralPath $signaturePath) { [System.IO.File]::Delete($signaturePath) }
& $minisign -S -s $secretKey -m $installer -x $signaturePath -t "Codex Theme Studio $cleanVersion"
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $signaturePath -PathType Leaf)) { throw 'Minisign update signing failed.' }
& $minisign -V -q -m $installer -x $signaturePath -P $publicKey
if ($LASTEXITCODE -ne 0) { throw 'Generated Minisign update signature failed verification.' }
$signatureText = [System.IO.File]::ReadAllText($signaturePath, [System.Text.Encoding]::UTF8)
if (-not $OutputPath) { $OutputPath = Join-Path (Split-Path -Parent $installer) 'latest.json' }
$output = [System.IO.Path]::GetFullPath($OutputPath)
$fileName = [System.IO.Path]::GetFileName($installer)
$manifest = [ordered]@{
  version = $cleanVersion
  notes = if ($Notes) { $Notes } else { "Codex Theme Studio $cleanVersion" }
  pub_date = [DateTime]::UtcNow.ToString('o')
  platforms = [ordered]@{
    'windows-x86_64' = [ordered]@{
      signature = $signatureText
      sha256 = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash
      url = "https://github.com/$Repository/releases/download/$ReleaseTagPrefix$cleanVersion/$fileName"
    }
  }
}
[System.IO.Directory]::CreateDirectory((Split-Path -Parent $output)) | Out-Null
[System.IO.File]::WriteAllText($output, ($manifest | ConvertTo-Json -Depth 6), [System.Text.UTF8Encoding]::new($false))
[pscustomobject]@{ status = 'COMPLETE'; manifest = $output; version = $cleanVersion; installer = $installer; signature = $signaturePath; authenticode = "$( (Get-AuthenticodeSignature -LiteralPath $installer).Status )" } | ConvertTo-Json
