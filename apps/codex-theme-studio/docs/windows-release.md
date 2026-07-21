# Windows 发布、签名与持续升级

## 当前发布模型

Codex Theme Studio 使用原生 WPF 客户端和 Inno Setup 离线 EXE 安装包。安装器使用固定 `AppId`，新版本会原位覆盖程序文件，并保留 `%LOCALAPPDATA%\CodexThemeStudio` 中的主题、备份和运行状态。

运行时内置经过固定 SHA-256 校验的 Node.js 24 LTS，仅用于执行页面渲染器；主题事务、Codex 会话、暂停、恢复、回退、验证和安装生命周期均由 .NET 引擎完成，不再依赖 PowerShell。

## CC Switch 式升级逻辑

客户端读取 GitHub Release 中固定地址的 `latest.json`，按 `windows-x86_64` 选择安装包并执行：

1. 比较清单版本与当前版本。
2. 只接受已配置仓库下的 HTTPS Release URL。
3. 下载 Windows EXE 到用户更新暂存目录。
4. 校验清单声明的 SHA-256。
5. 使用编译进当前客户端的 Minisign/Ed25519 公钥验证安装包签名。
6. 安装前再次校验 SHA-256 与 Minisign 签名。
7. 静默启动固定 `AppId` 的安装器完成原位升级。

Minisign 公钥位于 `assets/update-public-key.txt`，同时被编译进客户端；验证器使用固定版本和 SHA-256 打包，运行前再次校验自身完整性。私钥不得进入源码、安装包、日志或 Release，只能保存在发布者的离线备份和 GitHub Actions Secret 中。

## 本地构建与发布

```powershell
.\scripts\build-windows-installer.ps1 `
  -AppVersion 2.5.1 `
  -GitHubRepository owner/codex-theme-studio `
  -UpdateReleaseTag latest `
  -SignMode None

.\scripts\new-update-manifest.ps1 `
  -Version 2.5.1 `
  -Repository owner/codex-theme-studio `
  -ReleaseTagPrefix v `
  -InstallerPath .\dist\Codex-Theme-Studio-Setup-2.5.1.exe `
  -SecretKeyPath <private-minisign-key>
```

清单脚本会生成安装包对应的 `.minisig`，把完整签名写入 `latest.json`，并在写清单前用公开密钥回验。

仓库中的 `.github/workflows/release.yml` 会在推送 `v*` 标签后，使用 GitHub 托管的 `windows-latest` Runner 完成构建、Minisign 签署、清单生成和 GitHub Release 发布，不再依赖代码签名硬件或自托管 Runner。

若客户端放在共享仓库，不能使用仓库级 `releases/latest`，否则其他项目的新 Release 会抢占更新端点。此时应给 Theme Studio 使用固定滚动标签，例如 `codex-theme-studio-latest`，并将版本包发布到 `codex-theme-studio-v<version>`；构建时分别传入 `-UpdateReleaseTag codex-theme-studio-latest` 与 `-ReleaseTagPrefix codex-theme-studio-v`。

首次配置仓库时，把私钥文件的原始字节做 Base64，并保存为 Actions Secret `MINISIGN_SECRET_KEY_BASE64`。不要把 Base64 文本写入仓库、Issue、Release 或构建日志。发布私钥一旦丢失，现有客户端将无法验证后续更新；至少保存一份离线加密备份。

## Windows Authenticode 的位置

当前发布链不要求 Authenticode。Minisign 负责证明“更新来自 Theme Studio 发布者且没有被篡改”，但不会让 Windows 显示受信任发布者，也不会消除 SmartScreen 或 UAC 的“未知发布者”提示。

将来取得受 Windows 信任的证书后，可以在不改变 `latest.json`、Minisign 公钥和既有客户端升级能力的前提下，额外签名：

- `CodexThemeStudio.exe`
- `Codex-Theme-Studio-Setup-<version>.exe`

现有脚本保留三种可选 Authenticode 来源：

- `Store`：USB Token、HSM 或云签名 KSP 中的证书。
- `ArtifactSigning`：Microsoft Artifact Signing。
- `Pfx`：只用于仍允许 PFX 的旧有或私有流程，密码必须从环境变量读取。

不能用自签名证书解决其他 Windows 电脑的信任问题。无证书阶段的预期行为是：安装包可正常安装和持续升级，但用户首次下载或每个新文件可能收到 SmartScreen 提示，企业策略也可能禁止绕过。取得证书后再叠加 Authenticode，不替换 Minisign 更新签名。

中国个人开发者的后续可选路径：

1. 有可验证企业主体时购买公开代码签名证书，选择 USB Token 或云 HSM。
2. 通过 Microsoft Store 分发 MSIX，由 Store 负责签名和更新；直接下载的 EXE 仍需自有 Authenticode 证书。
3. 继续 GitHub 直接下载并使用当前 Minisign 更新签名，但不得宣称 Windows“受信任发布者”。

官方依据：

- [Tauri Updater 签名机制](https://v2.tauri.app/plugin/updater/#signing-updates)
- [Minisign 官方项目](https://github.com/jedisct1/minisign)
- [SmartScreen 发布者信誉](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation)
- [Microsoft Store 开发者账号](https://learn.microsoft.com/en-us/windows/apps/publish/partner-center/open-a-developer-account)

## 发布验收

正式发布前必须验证更新签名；Authenticode 状态在无证书阶段预期为 `NotSigned`：

```powershell
$publicKey = (Get-Content -Raw .\assets\update-public-key.txt).Trim()
.\build\windows\runtime\runtime\minisign.exe -Vm `
  .\dist\Codex-Theme-Studio-Setup-2.5.1.exe `
  -x .\dist\Codex-Theme-Studio-Setup-2.5.1.exe.minisig `
  -P $publicKey

Get-AuthenticodeSignature .\dist\Codex-Theme-Studio-Setup-2.5.1.exe
```

Minisign 必须返回成功，`latest.json` 中的 SHA-256 必须与安装包一致。随后在未安装 Node.js、未安装 PowerShell 7、没有旧 Theme Studio 状态的干净 Windows 10/11 x64 虚拟机中验证 SmartScreen 提示后的安装、切换、托盘、升级和卸载。
