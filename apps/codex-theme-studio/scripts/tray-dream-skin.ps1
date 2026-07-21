[CmdletBinding()]
param([int]$Port = 9335)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName Microsoft.VisualBasic
if (-not ('CodexThemeStudioTrayNative' -as [type])) {
  Add-Type @'
using System.Runtime.InteropServices;
public static class CodexThemeStudioTrayNative {
  [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
  public static extern int SetCurrentProcessExplicitAppUserModelID(string appId);
}
'@
}
try { [void][CodexThemeStudioTrayNative]::SetCurrentProcessExplicitAppUserModelID('CodexThemeStudio.Desktop') } catch { }
. (Join-Path $PSScriptRoot 'common-windows.ps1')
. (Join-Path $PSScriptRoot 'theme-windows.ps1')

Assert-DreamSkinPort -Port $Port
$SkillRoot = Split-Path -Parent $PSScriptRoot
$StateRoot = Join-Path $env:LOCALAPPDATA 'CodexThemeStudio'
$paths = Initialize-DreamSkinThemeStore -SkillRoot $SkillRoot -StateRoot $StateRoot
$powershell = (Get-Command powershell.exe -ErrorAction Stop).Source
$startScript = Join-Path $PSScriptRoot 'start-dream-skin.ps1'
$restoreScript = Join-Path $PSScriptRoot 'restore-dream-skin.ps1'
$studioScript = Join-Path $PSScriptRoot 'theme-studio.ps1'

$sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$mutex = [System.Threading.Mutex]::new($false, "Local\CodexThemeStudio.$sid.Tray")
$acquired = $false
try {
  try { $acquired = $mutex.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $acquired = $true }
  if (-not $acquired) { exit 0 }

  # NOTE: 原生 TCP 表类型在托盘后台启动时预热，避免第一次右键菜单承担 Add-Type 编译成本。
  Initialize-DreamSkinTcpTable

  $notify = [System.Windows.Forms.NotifyIcon]::new()
  $studioIcon = $null
  $studioIconPath = Join-Path $SkillRoot 'assets\studio.ico'
  if (Test-Path -LiteralPath $studioIconPath -PathType Leaf) {
    $studioIcon = [System.Drawing.Icon]::new($studioIconPath)
    $notify.Icon = $studioIcon
  } else {
    $notify.Icon = [System.Drawing.SystemIcons]::Application
  }
  $notify.Text = 'Codex Theme Studio'
  $notify.Visible = $true
  $menu = [System.Windows.Forms.ContextMenuStrip]::new()
  $notify.ContextMenuStrip = $menu

  function Show-DreamSkinTrayError {
    param([string]$Message)
    [void][System.Windows.Forms.MessageBox]::Show(
      $Message,
      'Codex Theme Studio',
      [System.Windows.Forms.MessageBoxButtons]::OK,
      [System.Windows.Forms.MessageBoxIcon]::Error
    )
  }

  function Start-DreamSkinPowerShell {
    param([Parameter(Mandatory = $true)][string]$Script, [string[]]$Arguments = @())
    $scriptToken = ConvertTo-DreamSkinProcessArgument -Value $Script
    $argumentLine = '-NoProfile -ExecutionPolicy RemoteSigned -File ' + $scriptToken
    if ($Arguments.Count -gt 0) { $argumentLine += ' ' + ($Arguments -join ' ') }
    Start-Process -FilePath $powershell -ArgumentList $argumentLine -WindowStyle Hidden | Out-Null
  }

  function Start-DreamSkinThemeRefresh {
    param([Parameter(Mandatory = $true)][string]$Message)
    Set-DreamSkinPaused -Paused $false -StateRoot $StateRoot | Out-Null
    $session = Get-DreamSkinLiveSessionContext -StateRoot $StateRoot
    $begin = $null
    if ($null -ne $session) {
      $begin = Show-DreamSkinOperationUi -Session $session -Phase begin -Kind switch -TimeoutMs 3000
    }
    # Restarting the watcher reloads both the selected theme and the current
    # engine CSS. A normally launched Codex gets an explicit restart prompt.
    Start-DreamSkinPowerShell -Script $startScript -Arguments @('-Port', "$Port", '-PromptRestart')
    if ($null -ne $session -and $null -ne $begin -and $begin.Ok) {
      $null = Show-DreamSkinOperationUi -Session $session -Phase finish -Token $begin.Token `
        -UiState success -Message '正在切换主题' -TimeoutMs 1500
    }
    $notify.ShowBalloonTip(2200, 'Codex Theme Studio', $Message, [System.Windows.Forms.ToolTipIcon]::Info)
  }

  function Add-DreamSkinTrayItem {
    param(
      [Parameter(Mandatory = $true)]
      [AllowEmptyCollection()]
      [System.Windows.Forms.ToolStripItemCollection]$Items,
      [Parameter(Mandatory = $true)][string]$Text,
      [AllowNull()][scriptblock]$Action,
      [bool]$Enabled = $true
    )
    $item = [System.Windows.Forms.ToolStripMenuItem]::new($Text)
    $item.Enabled = $Enabled
    if ($null -ne $Action) {
      $item.add_Click({
        try { & $Action } catch { Show-DreamSkinTrayError -Message $_.Exception.Message }
      }.GetNewClosure())
    }
    [void]$Items.Add($item)
    return $item
  }

  function Rebuild-DreamSkinTrayMenu {
    $menu.Items.Clear()
    $paused = Test-DreamSkinPaused -StateRoot $StateRoot
    $state = $null
    try { $state = Read-DreamSkinState -Path $paths.State } catch {}
    $session = Get-DreamSkinLiveSessionContext -StateRoot $StateRoot
    $active = $null
    try { $active = Read-DreamSkinTheme -ThemeDirectory $paths.Active -SkipImageMetadata } catch {}
    $status = if ($paused) {
      '状态：已暂停'
    } elseif ($null -ne $session) {
      '状态：运行中'
    } elseif ($null -ne $state) {
      '状态：需重新应用'
    } else {
      '状态：未运行'
    }
    if ($null -ne $active -and $null -ne $active.Theme -and $active.Theme.name) {
      $status += " · $($active.Theme.name)"
    }
    if ($null -ne $state -and $state.previousThemeId) { $status += " · 上一个：$($state.previousThemeId)" }
    $null = Add-DreamSkinTrayItem -Items $menu.Items -Text $status -Action $null -Enabled $false
    [void]$menu.Items.Add([System.Windows.Forms.ToolStripSeparator]::new())

    $null = Add-DreamSkinTrayItem -Items $menu.Items -Text '应用或重新应用' -Action {
      Set-DreamSkinPaused -Paused $false -StateRoot $StateRoot | Out-Null
      $session = Get-DreamSkinLiveSessionContext -StateRoot $StateRoot
      $begin = $null
      if ($null -ne $session) {
        $begin = Show-DreamSkinOperationUi -Session $session -Phase begin -Kind apply -TimeoutMs 3000
      }
      Start-DreamSkinPowerShell -Script $startScript -Arguments @('-Port', "$Port", '-PromptRestart')
      # start-dream-skin is async; close the in-window loading so it does not stick for 180s.
      if ($null -ne $session -and $null -ne $begin -and $begin.Ok) {
        $null = Show-DreamSkinOperationUi -Session $session -Phase finish -Token $begin.Token `
          -UiState success -Message '已开始应用皮肤' -TimeoutMs 1500
      }
      $notify.ShowBalloonTip(1800, 'Codex Theme Studio', '正在应用皮肤…', [System.Windows.Forms.ToolTipIcon]::Info)
    }
    # Match macOS menubar: pause = mark + live remove; resume = clear pause + re-apply.
    if ($paused) {
      $null = Add-DreamSkinTrayItem -Items $menu.Items -Text '继续显示皮肤' -Action {
        # Match macOS: clear pause + apply path; show in-window loading when CDP is up.
        Set-DreamSkinPaused -Paused $false -StateRoot $StateRoot | Out-Null
        $session = Get-DreamSkinLiveSessionContext -StateRoot $StateRoot
        $begin = $null
        if ($null -ne $session) {
          $begin = Show-DreamSkinOperationUi -Session $session -Phase begin -Kind apply -TimeoutMs 3000
        }
        Start-DreamSkinPowerShell -Script $startScript -Arguments @('-Port', "$Port", '-PromptRestart')
        if ($null -ne $session -and $null -ne $begin -and $begin.Ok) {
          $null = Show-DreamSkinOperationUi -Session $session -Phase finish -Token $begin.Token `
            -UiState success -Message '已开始重新应用皮肤' -TimeoutMs 1500
        }
        $notify.ShowBalloonTip(
          1800,
          'Codex Theme Studio',
          '正在重新应用皮肤…',
          [System.Windows.Forms.ToolTipIcon]::Info
        )
      }
    } else {
      $null = Add-DreamSkinTrayItem -Items $menu.Items -Text '暂停皮肤' -Action {
        # Match macOS pause: marker + live remove with in-window loading / result.
        Set-DreamSkinPaused -Paused $true -StateRoot $StateRoot | Out-Null
        $removal = Invoke-DreamSkinLiveRemove -StateRoot $StateRoot
        $icon = if ($removal.Removed) {
          [System.Windows.Forms.ToolTipIcon]::Info
        } else {
          [System.Windows.Forms.ToolTipIcon]::Warning
        }
        $notify.ShowBalloonTip(2800, 'Codex Theme Studio', $removal.Message, $icon)
        if (-not $removal.Removed -and $removal.Attempted) {
          Show-DreamSkinTrayError -Message $removal.Message
        }
      }
    }
    $savedMenu = [System.Windows.Forms.ToolStripMenuItem]::new('已保存主题')
    $savedThemes = @(Get-DreamSkinSavedThemes -StateRoot $StateRoot -SkipImageMetadata)
    if ($savedThemes.Count -eq 0) {
      $empty = [System.Windows.Forms.ToolStripMenuItem]::new('暂无已保存主题')
      $empty.Enabled = $false
      [void]$savedMenu.DropDownItems.Add($empty)
    } else {
      foreach ($saved in $savedThemes) {
        $savedPath = $saved.Path
        $savedName = $saved.Name
        $savedId = $saved.Id
        $savedAction = {
          Start-DreamSkinPowerShell -Script $studioScript -Arguments @('activate', $savedId, '-RestartExisting', '-Port', "$Port")
          $notify.ShowBalloonTip(2200, 'Codex Theme Studio', "正在切换：$savedName", [System.Windows.Forms.ToolTipIcon]::Info)
        }.GetNewClosure()
        $null = Add-DreamSkinTrayItem -Items $savedMenu.DropDownItems -Text $savedName -Action $savedAction
      }
    }
    [void]$menu.Items.Add($savedMenu)

    $previousAvailable = Test-Path -LiteralPath (Join-Path $StateRoot 'backups\previous-theme\theme.json') -PathType Leaf
    $null = Add-DreamSkinTrayItem -Items $menu.Items -Text '回退上一主题' -Enabled $previousAvailable -Action {
      Start-DreamSkinPowerShell -Script $studioScript -Arguments @('rollback', '-Port', "$Port")
    }

    $null = Add-DreamSkinTrayItem -Items $menu.Items -Text '打开主题文件夹' -Action {
      Start-Process -FilePath explorer.exe -ArgumentList @($paths.Saved) | Out-Null
    }
    [void]$menu.Items.Add([System.Windows.Forms.ToolStripSeparator]::new())
    $null = Add-DreamSkinTrayItem -Items $menu.Items -Text '恢复官方外观（保留主题）' -Action {
      Start-DreamSkinPowerShell -Script $studioScript -Arguments @('restore', '-Port', "$Port")
    }
    $null = Add-DreamSkinTrayItem -Items $menu.Items -Text '完全恢复 Codex' -Action {
      Start-DreamSkinPowerShell -Script $restoreScript -Arguments @(
        '-Port', "$Port", '-RestoreBaseTheme', '-PromptRestart'
      )
      $notify.Visible = $false
      [System.Windows.Forms.Application]::Exit()
    }
    $null = Add-DreamSkinTrayItem -Items $menu.Items -Text '退出托盘' -Action {
      $notify.Visible = $false
      [System.Windows.Forms.Application]::Exit()
    }
  }

  $menu.add_Opening({ Rebuild-DreamSkinTrayMenu })
  $notify.add_DoubleClick({
    try {
      Set-DreamSkinPaused -Paused $false -StateRoot $StateRoot | Out-Null
      Start-DreamSkinPowerShell -Script $startScript -Arguments @('-Port', "$Port", '-PromptRestart')
    } catch {
      Show-DreamSkinTrayError -Message $_.Exception.Message
    }
  })
  [System.Windows.Forms.Application]::Run()
} finally {
  if ($null -ne $notify) { $notify.Dispose() }
  if ($null -ne $studioIcon) { $studioIcon.Dispose() }
  if ($acquired) { try { $mutex.ReleaseMutex() } catch {} }
  $mutex.Dispose()
}
