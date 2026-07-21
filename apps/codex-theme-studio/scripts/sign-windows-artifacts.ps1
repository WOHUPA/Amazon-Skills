[CmdletBinding()]
param(
  [Parameter(Mandatory)][ValidateSet('Store','Pfx','ArtifactSigning')][string]$Mode,
  [Parameter(Mandatory)][string[]]$Path,
  [string]$CertificateThumbprint,
  [string]$PfxPath,
  [string]$PfxPasswordEnvironmentVariable = 'CODEX_THEME_PFX_PASSWORD',
  [string]$TimestampUrl = 'http://timestamp.digicert.com',
  [string]$ArtifactSigningDlib,
  [string]$ArtifactSigningMetadata
)

$ErrorActionPreference = 'Stop'

function Get-SignTool {
  $candidates = @(
    Get-ChildItem -Path "${env:ProgramFiles(x86)}\Windows Kits\10\bin" -Recurse -Filter signtool.exe -ErrorAction SilentlyContinue |
      Where-Object FullName -Match '\\x64\\signtool\.exe$' |
      Sort-Object FullName -Descending |
      Select-Object -ExpandProperty FullName
  )
  $tool = $candidates | Select-Object -First 1
  if (-not $tool) { throw 'Windows SDK x64 SignTool.exe was not found.' }
  return $tool
}

$signTool = Get-SignTool
$targets = @($Path | ForEach-Object { [System.IO.Path]::GetFullPath($_) })
foreach ($target in $targets) {
  if (-not (Test-Path -LiteralPath $target -PathType Leaf)) { throw "Signing target does not exist: $target" }
}

foreach ($target in $targets) {
  $arguments = @('sign','/v','/fd','SHA256','/d','Codex Theme Studio')
  if ($Mode -eq 'Store') {
    if (-not $CertificateThumbprint) { throw 'Store signing requires -CertificateThumbprint.' }
    $thumbprint = ($CertificateThumbprint -replace '[^A-Fa-f0-9]','').ToUpperInvariant()
    if ($thumbprint.Length -lt 40) { throw 'Certificate thumbprint is invalid.' }
    $arguments += @('/sha1',$thumbprint,'/tr',$TimestampUrl,'/td','SHA256')
  } elseif ($Mode -eq 'Pfx') {
    if (-not $PfxPath -or -not (Test-Path -LiteralPath $PfxPath -PathType Leaf)) { throw 'PFX signing requires a valid -PfxPath.' }
    $password = [Environment]::GetEnvironmentVariable($PfxPasswordEnvironmentVariable)
    if (-not $password) { throw "PFX password environment variable is missing: $PfxPasswordEnvironmentVariable" }
    $arguments += @('/f',[System.IO.Path]::GetFullPath($PfxPath),'/p',$password,'/tr',$TimestampUrl,'/td','SHA256')
  } else {
    foreach ($required in @($ArtifactSigningDlib,$ArtifactSigningMetadata)) {
      if (-not $required -or -not (Test-Path -LiteralPath $required -PathType Leaf)) { throw "Artifact Signing dependency is missing: $required" }
    }
    $arguments += @(
      '/debug','/tr','http://timestamp.acs.microsoft.com','/td','SHA256',
      '/dlib',[System.IO.Path]::GetFullPath($ArtifactSigningDlib),
      '/dmdf',[System.IO.Path]::GetFullPath($ArtifactSigningMetadata)
    )
  }
  $arguments += $target
  & $signTool @arguments
  if ($LASTEXITCODE -ne 0) { throw "SignTool failed for $target with exit code $LASTEXITCODE." }
  & $signTool verify /pa /all /v $target
  if ($LASTEXITCODE -ne 0) { throw "Authenticode verification failed for $target." }
}

[pscustomobject]@{
  status = 'COMPLETE'
  mode = $Mode
  files = @($targets | ForEach-Object {
    $signature = Get-AuthenticodeSignature -LiteralPath $_
    [pscustomobject]@{ path = $_; status = "$($signature.Status)"; subject = if ($signature.SignerCertificate) { $signature.SignerCertificate.Subject } else { $null } }
  })
} | ConvertTo-Json -Depth 5
