# Windows 发布、签名与持续升级

## 当前发布模型

Codex Theme Studio 2.7 继续以 WiX MSI 为 Windows 主安装包。MSI 使用稳定 `UpgradeCode` 和按版本确定生成的 `ProductCode`，安装到 `%LOCALAPPDATA%\Programs\Codex Theme Studio`，由 Windows Installer 提供原位升级、修复、卸载和失败事务回滚。

每个版本暂时同时生成两种文件：

- `Codex-Theme-Studio-<version>-Windows-x64.msi`：2.6+ 客户端和新用户使用的正式安装包。
- `Codex-Theme-Studio-Setup-<version>.exe`：只供仍安装 2.5.x 的用户进入 MSI 更新线。桥接完成后，新客户端只读取 MSI 平台项。

运行时内置经过固定 SHA-256 校验的 Node.js 24 LTS，仅用于页面渲染器。主题事务、Codex 会话、暂停、恢复、回退、验证和安装生命周期均由 .NET 引擎完成。

## 事务式升级链路

客户端读取固定 GitHub Release 中的 `latest.json`，按平台选择安装包：

- 旧版：`windows-x86_64`，对应桥接 EXE。
- 新版：`windows-x86_64-msi`，对应正式 MSI。

新链路依次执行：

1. 比较远端版本；远端不高于本机时不要求旧清单包含 MSI 平台项。
2. 只接受配置仓库下的 HTTPS GitHub Release URL。
3. 断点续传 MSI，失败时最多重试三次。
4. 校验 SHA-256，并用客户端内置公钥环验证一个或多个 Minisign 签名。
5. 校验安装目录中的独立更新器哈希，把更新器复制到版本暂存目录。
6. 写入 `transaction.json`，启动更新器并退出主程序。
7. 更新器等待主程序完全退出，再次校验 SHA-256、Minisign 和验证器自身哈希。
8. 通过 `msiexec /passive /norestart /L*v` 安装；Windows Installer 失败时自动回滚文件与注册状态。
9. 安装后检查磁盘中 `CodexThemeStudio.exe` 的实际版本，写入安装日志与最终回执。
10. 成功或失败均重新打开客户端；失败时旧版本继续可用，并展示回执中的原因。

更新文件位于 `%LOCALAPPDATA%\CodexThemeStudio\updates\<version>`。完整 MSI 日志保存在事务目录的 `install.log`。

## 公钥轮换

`assets/update-public-key.txt` 是当前发布密钥，`assets/update-public-keys.txt` 是编译进客户端的受信任公钥环。发布私钥只能保存在发布者的离线加密备份和 GitHub Actions Secret 中。

轮换时不能直接删除旧公钥：

1. 先把新公钥加入公钥环。
2. 使用旧私钥和新私钥同时签署一个过渡版本；清单的 `signatures` 数组包含两个签名。
3. 等待主要用户升级到过渡版本。
4. 后续版本改用新私钥；确认旧客户端占比可接受后再移除旧公钥。

私钥丢失且没有提前发布包含新公钥的过渡版本时，现有客户端无法信任新更新。

## 本地构建

构建脚本从官方 NuGet 下载 WiX 3.14.1 便携工具链并校验固定 SHA-256，不要求管理员安装 WiX。Inno Setup 6 仅用于生成旧版桥接 EXE。

```powershell
winget install --id JRSoftware.InnoSetup --exact --accept-source-agreements --accept-package-agreements

.\scripts\build-windows-installer.ps1 `
  -AppVersion 2.7.2 `
  -GitHubRepository WOHUPA/Amazon-Skills `
  -UpdateReleaseTag codex-theme-studio-latest `
  -SignMode None
```

生成清单和签名：

```powershell
.\scripts\new-update-manifest.ps1 `
  -Version 2.7.2 `
  -Repository WOHUPA/Amazon-Skills `
  -ReleaseTagPrefix codex-theme-studio-v `
  -InstallerPath .\dist\Codex-Theme-Studio-2.7.2-Windows-x64.msi `
  -BridgeInstallerPath .\dist\Codex-Theme-Studio-Setup-2.7.2.exe `
  -SecretKeyPath <private-minisign-key>
```

多个 `-SecretKeyPath` 会产生多个签名，用于公钥轮换过渡。

## GitHub 发布

共享仓库不能使用仓库级 `releases/latest`，否则其他项目的新 Release 会抢占端点。本项目使用：

- 版本 Release：`codex-theme-studio-v<version>`。
- 固定滚动清单：`codex-theme-studio-latest/latest.json`。

根工作流 `.github/workflows/codex-theme-studio-release.yml` 在推送 `codex-theme-studio-v*` 标签后构建 MSI 与桥接 EXE，使用 `MINISIGN_SECRET_KEY_BASE64` 签署两个安装包，发布版本资产并更新滚动清单。

## Windows Authenticode

Minisign 证明更新来自项目发布密钥且内容未被篡改，但不会消除 SmartScreen 的“未知发布者”提示。取得受信任代码签名证书后，应额外签名：

- `CodexThemeStudio.exe`
- `CodexThemeStudio.Updater.exe`
- MSI 和桥接 EXE

不能用自签名证书解决其他电脑的 Windows 信任问题。当前无证书发布可安装和持续升级，但首次下载仍可能出现 SmartScreen，企业策略也可能禁止绕过。

## 发布验收

每次正式发布至少验证：

1. MSI 与桥接 EXE 的 SHA-256、`.minisig` 和 `latest.json` 完全一致。
2. 正确安装包通过，篡改一个字节后必须被拒绝。
3. 2.5.x EXE 安装形态可以迁移到 MSI，主题和状态不丢失，旧 Inno 卸载项被清理。
4. MSI 旧版升级到新版后只保留一个 Windows Installer 卸载项。
5. 主程序运行时升级不会锁死；更新器能等待退出、写日志、校验版本并重新启动。
6. 安装失败时 Windows Installer 回滚，客户端能读取失败回执并继续启动旧版本。
7. Windows 10/11 x64 干净虚拟机上完成安装、切换、托盘、修复、升级和卸载测试。
