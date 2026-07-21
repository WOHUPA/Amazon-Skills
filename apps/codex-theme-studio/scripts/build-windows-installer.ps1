[CmdletBinding()]
param(
  [string]$AppVersion = '2.6.0',
  [string]$GitHubRepository = '',
  [string]$UpdateReleaseTag = 'latest',
  [string]$NodeVersion = '24.18.0',
  [ValidateSet('None','Store','Pfx','ArtifactSigning')][string]$SignMode = 'None',
  [string]$CertificateThumbprint,
  [string]$PfxPath,
  [string]$ArtifactSigningDlib,
  [string]$ArtifactSigningMetadata,
  [switch]$RequireSigned
)

$ErrorActionPreference = 'Stop'
$root = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$buildRoot = Join-Path $root 'build\windows'
$payloadRoot = Join-Path $buildRoot 'runtime'
$distRoot = Join-Path $root 'dist'
$launcherSource = Join-Path $root 'desktop\Launcher.cs'
$clientSource = Join-Path $root 'desktop\StudioClient.cs'
$engineSource = Join-Path $root 'desktop\ThemeEngine.cs'
$updateSource = Join-Path $root 'desktop\UpdateService.cs'
$updaterSource = Join-Path $root 'desktop\Updater.cs'
$updatePublicKeyFile = Join-Path $root 'assets\update-public-key.txt'
$updatePublicKeysFile = Join-Path $root 'assets\update-public-keys.txt'
$installerSource = Join-Path $root 'installer\CodexThemeStudio.iss'
$wixSource = Join-Path $root 'installer\CodexThemeStudio.wxs'
$licenseRtf = Join-Path $root 'installer\license.rtf'
$versionFile = Join-Path $root 'assets\studio-version.txt'
$iconSource = Join-Path $root 'assets\studio-icon.png'
$runtimeIcon = Join-Path $root 'assets\studio.ico'
$signScript = Join-Path $root 'scripts\sign-windows-artifacts.ps1'
$csc = 'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$presentationCore = (Get-ChildItem 'C:\Windows\Microsoft.NET\assembly\GAC_32\PresentationCore' -Recurse -Filter PresentationCore.dll -ErrorAction Stop | Select-Object -First 1).FullName
$presentationFramework = (Get-ChildItem 'C:\Windows\Microsoft.NET\assembly\GAC_MSIL\PresentationFramework' -Recurse -Filter PresentationFramework.dll -ErrorAction Stop | Select-Object -First 1).FullName
$windowsBase = (Get-ChildItem 'C:\Windows\Microsoft.NET\assembly\GAC_MSIL\WindowsBase' -Recurse -Filter WindowsBase.dll -ErrorAction Stop | Select-Object -First 1).FullName
$systemXaml = (Get-ChildItem 'C:\Windows\Microsoft.NET\assembly\GAC_MSIL\System.Xaml' -Recurse -Filter System.Xaml.dll -ErrorAction Stop | Select-Object -First 1).FullName

foreach ($required in @($launcherSource, $clientSource, $engineSource, $updateSource, $updaterSource, $updatePublicKeyFile, $updatePublicKeysFile, $installerSource, $wixSource, $licenseRtf, $versionFile, $iconSource, $signScript,$csc,$presentationCore,$presentationFramework,$windowsBase,$systemXaml)) {
  if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
    throw "Windows installer build dependency is missing: $required"
  }
}
$declaredVersion = (Get-Content -Raw -LiteralPath $versionFile -Encoding UTF8).Trim()
if ($declaredVersion -cne $AppVersion) {
  throw "AppVersion $AppVersion does not match assets/studio-version.txt ($declaredVersion)."
}
if ($UpdateReleaseTag -cnotmatch '^[A-Za-z0-9_.-]+$') { throw 'UpdateReleaseTag contains unsupported characters.' }

function Remove-ManagedBuildDirectory([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path)) { return }
  $full = [System.IO.Path]::GetFullPath($Path)
  $allowed = [System.IO.Path]::GetFullPath($buildRoot).TrimEnd('\')
  if ($full -cne $allowed -and -not $full.StartsWith($allowed + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to clean outside the managed build directory: $full"
  }
  [System.IO.Directory]::Delete($full, $true)
}

function New-StudioIcon([string]$SourcePath, [string]$Path) {
  Add-Type -AssemblyName System.Drawing
  $source = [System.Drawing.Image]::FromFile($SourcePath)
  try {
    $frames = @()
    foreach ($size in @(16,20,24,32,40,48,64,128,256)) {
      $bitmap = [System.Drawing.Bitmap]::new($size, $size, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
      $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
      $stream = [System.IO.MemoryStream]::new()
      try {
        $graphics.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceCopy
        $graphics.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
        $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
        $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
        $graphics.DrawImage($source, 0, 0, $size, $size)
        $bitmap.Save($stream, [System.Drawing.Imaging.ImageFormat]::Png)
        $frames += [pscustomobject]@{ Size = $size; Bytes = $stream.ToArray() }
      } finally {
        $stream.Dispose(); $graphics.Dispose(); $bitmap.Dispose()
      }
    }
    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    $file = [System.IO.File]::Open($Path, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write)
    $writer = [System.IO.BinaryWriter]::new($file)
    try {
      $writer.Write([uint16]0); $writer.Write([uint16]1); $writer.Write([uint16]$frames.Count)
      $offset = 6 + (16 * $frames.Count)
      foreach ($frame in $frames) {
        $dimension = if ($frame.Size -eq 256) { 0 } else { $frame.Size }
        $writer.Write([byte]$dimension); $writer.Write([byte]$dimension)
        $writer.Write([byte]0); $writer.Write([byte]0)
        $writer.Write([uint16]1); $writer.Write([uint16]32)
        $writer.Write([uint32]$frame.Bytes.Length); $writer.Write([uint32]$offset)
        $offset += $frame.Bytes.Length
      }
      foreach ($frame in $frames) { $writer.Write([byte[]]$frame.Bytes) }
    } finally { $writer.Dispose(); $file.Dispose() }
  } finally { $source.Dispose() }
}

Remove-ManagedBuildDirectory -Path $buildRoot
New-Item -ItemType Directory -Path $payloadRoot -Force | Out-Null
New-Item -ItemType Directory -Path $distRoot -Force | Out-Null
New-StudioIcon -SourcePath $iconSource -Path $runtimeIcon

foreach ($directory in @('assets','presets','references')) {
  Copy-Item -LiteralPath (Join-Path $root $directory) -Destination $payloadRoot -Recurse -Force
}
# The installed client is .NET-native. Legacy preset scripts remain source
# references only and must never be shipped as executable PowerShell payloads.
Get-ChildItem -LiteralPath $payloadRoot -Recurse -Filter '*.ps1' -File | Remove-Item -Force
New-Item -ItemType Directory -Path (Join-Path $payloadRoot 'scripts') -Force | Out-Null
Copy-Item -Path (Join-Path $root 'scripts\*.mjs') -Destination (Join-Path $payloadRoot 'scripts') -Force

$nodeHashes = @{ '24.18.0' = '0ae68406b42d7725661da979b1403ec9926da205c6770827f33aac9d8f26e821' }
if (-not $nodeHashes.ContainsKey($NodeVersion)) { throw "Node.js version is not pinned in the build script: $NodeVersion" }
$nodeCache = Join-Path $env:LOCALAPPDATA "CodexThemeStudioBuildCache\node-v$NodeVersion-win-x64"
$nodeZip = "$nodeCache.zip"
if (-not (Test-Path -LiteralPath $nodeZip -PathType Leaf) -or
    (Get-FileHash -LiteralPath $nodeZip -Algorithm SHA256).Hash -ine $nodeHashes[$NodeVersion]) {
  New-Item -ItemType Directory -Path (Split-Path -Parent $nodeCache) -Force | Out-Null
  $download = "$nodeZip.download"
  $ProgressPreference = 'SilentlyContinue'
  Invoke-WebRequest -UseBasicParsing -Uri "https://nodejs.org/dist/v$NodeVersion/node-v$NodeVersion-win-x64.zip" -OutFile $download
  if ((Get-FileHash -LiteralPath $download -Algorithm SHA256).Hash -ine $nodeHashes[$NodeVersion]) {
    [System.IO.File]::Delete($download)
    throw 'Downloaded Node.js runtime failed SHA-256 verification.'
  }
  if (Test-Path -LiteralPath $nodeZip -PathType Leaf) { [System.IO.File]::Delete($nodeZip) }
  [System.IO.File]::Move($download, $nodeZip)
}
if (-not (Test-Path -LiteralPath (Join-Path $nodeCache 'node.exe') -PathType Leaf)) {
  if (Test-Path -LiteralPath $nodeCache) { [System.IO.Directory]::Delete($nodeCache, $true) }
  $nodeExtract = "$nodeCache.extract"
  if (Test-Path -LiteralPath $nodeExtract) { [System.IO.Directory]::Delete($nodeExtract, $true) }
  Expand-Archive -LiteralPath $nodeZip -DestinationPath $nodeExtract -Force
  [System.IO.Directory]::Move((Join-Path $nodeExtract "node-v$NodeVersion-win-x64"), $nodeCache)
  [System.IO.Directory]::Delete($nodeExtract, $true)
}
$runtimeBin = Join-Path $payloadRoot 'runtime'
New-Item -ItemType Directory -Path $runtimeBin -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $nodeCache 'node.exe') -Destination $runtimeBin -Force
Copy-Item -LiteralPath (Join-Path $nodeCache 'LICENSE') -Destination (Join-Path $runtimeBin 'NODE-LICENSE.txt') -Force

$minisignVersion = '0.12'
$minisignZipHash = '37B600344E20C19314B2E82813DB2BFDCC408B77B876F7727889DBD46D539479'
$minisignExeHash = '5535BE9E4E123831EBE6EF324AAFE9DDE507015C176191F9E20C3AD60567F9E1'
$minisignCacheRoot = Join-Path $env:LOCALAPPDATA "CodexThemeStudioBuildCache\minisign-$minisignVersion-win64"
$minisignZip = "$minisignCacheRoot.zip"
if (-not (Test-Path -LiteralPath $minisignZip -PathType Leaf) -or
    (Get-FileHash -LiteralPath $minisignZip -Algorithm SHA256).Hash -ine $minisignZipHash) {
  New-Item -ItemType Directory -Path (Split-Path -Parent $minisignCacheRoot) -Force | Out-Null
  $minisignDownload = "$minisignZip.download"
  Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/jedisct1/minisign/releases/download/$minisignVersion/minisign-$minisignVersion-win64.zip" -OutFile $minisignDownload
  if ((Get-FileHash -LiteralPath $minisignDownload -Algorithm SHA256).Hash -ine $minisignZipHash) {
    [System.IO.File]::Delete($minisignDownload)
    throw 'Downloaded Minisign archive failed SHA-256 verification.'
  }
  if (Test-Path -LiteralPath $minisignZip -PathType Leaf) { [System.IO.File]::Delete($minisignZip) }
  [System.IO.File]::Move($minisignDownload, $minisignZip)
}
$cachedMinisign = Join-Path $minisignCacheRoot 'minisign-win64\x86_64\minisign.exe'
if (-not (Test-Path -LiteralPath $cachedMinisign -PathType Leaf) -or
    (Get-FileHash -LiteralPath $cachedMinisign -Algorithm SHA256).Hash -ine $minisignExeHash) {
  if (Test-Path -LiteralPath $minisignCacheRoot) { [System.IO.Directory]::Delete($minisignCacheRoot, $true) }
  Expand-Archive -LiteralPath $minisignZip -DestinationPath $minisignCacheRoot -Force
}
if ((Get-FileHash -LiteralPath $cachedMinisign -Algorithm SHA256).Hash -ine $minisignExeHash) {
  throw 'Extracted Minisign verifier failed SHA-256 verification.'
}
Copy-Item -LiteralPath $cachedMinisign -Destination (Join-Path $runtimeBin 'minisign.exe') -Force

$updatePublicKey = (Get-Content -Raw -LiteralPath $updatePublicKeyFile -Encoding UTF8).Trim()
$updatePublicKeys = @(Get-Content -LiteralPath $updatePublicKeysFile -Encoding UTF8 | ForEach-Object { $_.Trim() } | Where-Object { $_ -and -not $_.StartsWith('#') })
if ($updatePublicKey -cnotmatch '^RW[A-Za-z0-9+/=]{50,}$' -or $updatePublicKeys.Count -eq 0 -or $updatePublicKeys -cnotcontains $updatePublicKey) {
  throw 'The trusted Minisign key ring is invalid or does not contain the current release key.'
}
foreach ($key in $updatePublicKeys) {
  if ($key -cnotmatch '^RW[A-Za-z0-9+/=]{50,}$') { throw "Invalid Minisign update public key: $key" }
}
$publicKeysCode = ($updatePublicKeys | ForEach-Object { '"' + $_ + '"' }) -join ', '

$updateConfig = [ordered]@{
  schemaVersion = 2
  repository = $GitHubRepository
  endpoint = if (-not $GitHubRepository) { '' } elseif ($UpdateReleaseTag -ceq 'latest') {
    "https://github.com/$GitHubRepository/releases/latest/download/latest.json"
  } else {
    "https://github.com/$GitHubRepository/releases/download/$UpdateReleaseTag/latest.json"
  }
  platform = 'windows-x86_64-msi'
}
$updateConfigPath = Join-Path $payloadRoot 'assets\update-channel.json'
[System.IO.File]::WriteAllText($updateConfigPath, ($updateConfig | ConvertTo-Json -Depth 4), [System.Text.UTF8Encoding]::new($false))
foreach ($cache in @(Get-ChildItem -LiteralPath $payloadRoot -Directory -Recurse -Force | Where-Object Name -eq '__pycache__')) {
  $cachePath = [System.IO.Path]::GetFullPath($cache.FullName)
  if (-not $cachePath.StartsWith([System.IO.Path]::GetFullPath($payloadRoot).TrimEnd('\') + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Unsafe cache path in runtime payload: $cachePath"
  }
  [System.IO.Directory]::Delete($cachePath, $true)
}
foreach ($bytecode in Get-ChildItem -LiteralPath $payloadRoot -File -Recurse -Filter '*.pyc' -Force) {
  [System.IO.File]::Delete($bytecode.FullName)
}

$runtimeZip = Join-Path $buildRoot 'theme-runtime.zip'
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory(
  $payloadRoot,
  $runtimeZip,
  [System.IO.Compression.CompressionLevel]::Optimal,
  $false
)

$icon = $runtimeIcon

function Invoke-StudioSigning([string[]]$Files) {
  if ($SignMode -eq 'None') {
    if ($RequireSigned) { throw 'A signed release was required, but -SignMode None was selected.' }
    return
  }
  $arguments = @{ Mode = $SignMode; Path = $Files }
  if ($CertificateThumbprint) { $arguments.CertificateThumbprint = $CertificateThumbprint }
  if ($PfxPath) { $arguments.PfxPath = $PfxPath }
  if ($ArtifactSigningDlib) { $arguments.ArtifactSigningDlib = $ArtifactSigningDlib }
  if ($ArtifactSigningMetadata) { $arguments.ArtifactSigningMetadata = $ArtifactSigningMetadata }
  & $signScript @arguments
  if ($LASTEXITCODE -ne 0) { throw 'Artifact signing failed.' }
}

$updaterTrustSource = Join-Path $buildRoot 'UpdaterTrust.g.cs'
$updaterTrustCode = @"
namespace CodexThemeStudio.Updater
{
    internal static class UpdateTrust
    {
        public static readonly string[] PublicKeys = new string[] { $publicKeysCode };
        public const string VerifierSha256 = "$minisignExeHash";
    }
}
"@
[System.IO.File]::WriteAllText($updaterTrustSource, $updaterTrustCode, [System.Text.UTF8Encoding]::new($false))
$updater = Join-Path $buildRoot 'CodexThemeStudio.Updater.exe'
& $csc '/nologo' '/target:winexe' '/optimize+' '/platform:x64' "/out:$updater" "/win32icon:$icon" `
  '/reference:System.dll' '/reference:System.Core.dll' '/reference:System.Web.Extensions.dll' $updaterSource $updaterTrustSource
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $updater -PathType Leaf)) {
  throw "CodexThemeStudio.Updater.exe compilation failed with exit code $LASTEXITCODE."
}
Invoke-StudioSigning -Files @($updater)
$updaterSha256 = (Get-FileHash -LiteralPath $updater -Algorithm SHA256).Hash

$updateTrustSource = Join-Path $buildRoot 'UpdateTrust.g.cs'
$updateTrustCode = @"
namespace CodexThemeStudio.Desktop
{
    internal static class UpdateTrust
    {
        public static readonly string[] PublicKeys = new string[] { $publicKeysCode };
        public const string VerifierSha256 = "$minisignExeHash";
        public const string UpdaterSha256 = "$updaterSha256";
    }
}
"@
[System.IO.File]::WriteAllText($updateTrustSource, $updateTrustCode, [System.Text.UTF8Encoding]::new($false))

$launcher = Join-Path $buildRoot 'CodexThemeStudio.exe'
$compilerArgs = @(
  '/nologo', '/target:winexe', '/optimize+', '/platform:x64',
  "/out:$launcher", "/win32icon:$icon", "/resource:$runtimeZip,CodexThemeStudio.Runtime.zip",
  '/reference:System.dll', '/reference:System.Core.dll', '/reference:System.Windows.Forms.dll',
  '/reference:System.Drawing.dll', "/reference:$systemXaml",
  "/reference:$windowsBase", "/reference:$presentationCore", "/reference:$presentationFramework",
  '/reference:System.IO.Compression.dll', '/reference:System.IO.Compression.FileSystem.dll',
  $launcherSource, $clientSource, $engineSource, $updateSource, $updateTrustSource
)
& $csc @compilerArgs
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $launcher -PathType Leaf)) {
  throw "CodexThemeStudio.exe compilation failed with exit code $LASTEXITCODE."
}
Invoke-StudioSigning -Files @($launcher)

$innoCandidates = @(
  (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
  (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'),
  (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe')
) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) }
$iscc = $innoCandidates | Select-Object -First 1
if (-not $iscc) {
  throw 'Inno Setup 6 is required. Install JRSoftware.InnoSetup with winget, then rerun this script.'
}

& $iscc "/DAppVersion=$AppVersion" "/DSourceExe=$launcher" "/DUpdaterExe=$updater" "/DOutputDir=$distRoot" "/DSetupIcon=$icon" $installerSource
if ($LASTEXITCODE -ne 0) { throw "Inno Setup compilation failed with exit code $LASTEXITCODE." }

$bridgeInstaller = Join-Path $distRoot "Codex-Theme-Studio-Setup-$AppVersion.exe"
if (-not (Test-Path -LiteralPath $bridgeInstaller -PathType Leaf)) { throw "Bridge installer output is missing: $bridgeInstaller" }
Invoke-StudioSigning -Files @($bridgeInstaller)

$wixVersion = '3.14.1'
$wixPackageHash = '15D50463C73DCE31FBEA5440AC33AF47E92D54D4188166D207E9E39577B8FE0F'
$wixCacheBase = Join-Path $env:LOCALAPPDATA 'CodexThemeStudioBuildCache'
$wixPackage = Join-Path $wixCacheBase "wix.$wixVersion.nupkg"
$wixCacheRoot = Join-Path $wixCacheBase "wix-$wixVersion"
if (-not (Test-Path -LiteralPath $wixPackage -PathType Leaf) -or
    (Get-FileHash -LiteralPath $wixPackage -Algorithm SHA256).Hash -ine $wixPackageHash) {
  New-Item -ItemType Directory -Path $wixCacheBase -Force | Out-Null
  $wixDownload = "$wixPackage.download"
  Invoke-WebRequest -UseBasicParsing -Uri "https://www.nuget.org/api/v2/package/wix/$wixVersion" -OutFile $wixDownload
  if ((Get-FileHash -LiteralPath $wixDownload -Algorithm SHA256).Hash -ine $wixPackageHash) {
    [System.IO.File]::Delete($wixDownload)
    throw 'Downloaded WiX NuGet package failed SHA-256 verification.'
  }
  if (Test-Path -LiteralPath $wixPackage) { [System.IO.File]::Delete($wixPackage) }
  [System.IO.File]::Move($wixDownload, $wixPackage)
}
$cachedCandle = Join-Path $wixCacheRoot 'tools\candle.exe'
$cachedLight = Join-Path $wixCacheRoot 'tools\light.exe'
if (-not (Test-Path -LiteralPath $cachedCandle -PathType Leaf) -or -not (Test-Path -LiteralPath $cachedLight -PathType Leaf)) {
  $resolvedWixCache = [System.IO.Path]::GetFullPath($wixCacheRoot)
  $allowedWixCache = [System.IO.Path]::GetFullPath($wixCacheBase).TrimEnd('\') + '\'
  if (-not $resolvedWixCache.StartsWith($allowedWixCache, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to replace an unsafe WiX cache path: $resolvedWixCache"
  }
  if (Test-Path -LiteralPath $resolvedWixCache) { [System.IO.Directory]::Delete($resolvedWixCache, $true) }
  [System.IO.Compression.ZipFile]::ExtractToDirectory($wixPackage, $resolvedWixCache)
}

$candleCandidates = @(
  $cachedCandle,
  (Join-Path ${env:ProgramFiles(x86)} 'WiX Toolset v3.14\bin\candle.exe'),
  (Join-Path ${env:ProgramFiles(x86)} 'WiX Toolset v3.11\bin\candle.exe'),
  (Get-Command candle.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1)
) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) }
$lightCandidates = @(
  $cachedLight,
  (Join-Path ${env:ProgramFiles(x86)} 'WiX Toolset v3.14\bin\light.exe'),
  (Join-Path ${env:ProgramFiles(x86)} 'WiX Toolset v3.11\bin\light.exe'),
  (Get-Command light.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1)
) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) }
$candle = $candleCandidates | Select-Object -First 1
$light = $lightCandidates | Select-Object -First 1
if (-not $candle -or -not $light) { throw 'WiX Toolset 3.14.1 is required to build the MSI package.' }
$wixObject = Join-Path $buildRoot 'CodexThemeStudio.wixobj'
$installer = Join-Path $distRoot "Codex-Theme-Studio-$AppVersion-Windows-x64.msi"
$productCodeBytes = [System.Security.Cryptography.MD5]::Create().ComputeHash([System.Text.Encoding]::UTF8.GetBytes("CodexThemeStudio.ProductCode/$AppVersion"))
$productCode = ([Guid]::new($productCodeBytes)).ToString('D').ToUpperInvariant()
$candleArgs = @(
  '-nologo', '-arch', 'x64',
  "-dAppVersion=$AppVersion", "-dProductCode=$productCode", "-dSourceExe=$launcher", "-dUpdaterExe=$updater",
  "-dSetupIcon=$icon", "-dLicenseRtf=$licenseRtf", "-out", $wixObject, $wixSource
)
& $candle @candleArgs
if ($LASTEXITCODE -ne 0) { throw "WiX candle compilation failed with exit code $LASTEXITCODE." }
# ICE91 is not applicable because this package intentionally supports per-user installation only.
& $light '-nologo' '-sice:ICE91' '-ext' 'WixUIExtension' '-out' $installer $wixObject
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $installer -PathType Leaf)) {
  throw "WiX light linking failed with exit code $LASTEXITCODE."
}
Invoke-StudioSigning -Files @($installer)
$launcherVersion = (Get-Item -LiteralPath $launcher).VersionInfo.ProductVersion
if ($launcherVersion -notlike "$AppVersion*") { throw "Launcher version mismatch: $launcherVersion" }

[pscustomobject]@{
  status = 'COMPLETE'
  appVersion = $AppVersion
  launcher = $launcher
  launcherBytes = (Get-Item -LiteralPath $launcher).Length
  updater = $updater
  updaterSha256 = $updaterSha256
  runtimeFiles = @(Get-ChildItem -LiteralPath $payloadRoot -File -Recurse).Count
  installer = $installer
  productCode = $productCode
  installerBytes = (Get-Item -LiteralPath $installer).Length
  bridgeInstaller = $bridgeInstaller
  bridgeInstallerBytes = (Get-Item -LiteralPath $bridgeInstaller).Length
  signMode = $SignMode
  signatureStatus = "$( (Get-AuthenticodeSignature -LiteralPath $installer).Status )"
  nodeVersion = $NodeVersion
  updateRepository = $GitHubRepository
  updateReleaseTag = $UpdateReleaseTag
  sha256 = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash
} | ConvertTo-Json -Depth 4
