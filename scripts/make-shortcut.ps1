# 创建桌面快捷方式。优先从已安装驱动中提取打印机图标，失败则用 Python 默认图标。
# 用法：.\scripts\make-shortcut.ps1 [-AppDir D:\path\to\p1007-controller]

param(
    [string]$AppDir = $PSScriptRoot | Split-Path
)

$ErrorActionPreference = "Stop"

$pythonw = Join-Path (Split-Path (Get-Command python).Source) "pythonw.exe"
if (-not (Test-Path $pythonw)) { $pythonw = (Get-Command python).Source }

# 尝试从驱动仓库里已安装的 HP 状态监视器提取图标
$iconFile = Join-Path $AppDir "printer.ico"
if (-not (Test-Path $iconFile)) {
    try {
        Add-Type -AssemblyName System.Drawing
        $src = Get-ChildItem "$env:SystemRoot\System32\spool\drivers", "$env:SystemRoot\INF" -Recurse -Filter "hp1006SM.exe" -ErrorAction SilentlyContinue |
            Select-Object -First 1 -ExpandProperty FullName
        if ($src) {
            $icon = [System.Drawing.Icon]::ExtractAssociatedIcon($src)
            $fs = [System.IO.File]::Create($iconFile)
            $icon.Save($fs); $fs.Close()
            Write-Host "已从 $src 提取图标"
        }
    } catch {
        Write-Host "图标提取失败，使用默认图标：$($_.Exception.Message)"
    }
}

$ws = New-Object -ComObject WScript.Shell
$lnkPath = Join-Path ([Environment]::GetFolderPath("Desktop")) "HP P1007 打印机上位机.lnk"
$lnk = $ws.CreateShortcut($lnkPath)
$lnk.TargetPath = $pythonw
$lnk.Arguments = '"{0}"' -f (Join-Path $AppDir "app.py")
$lnk.WorkingDirectory = $AppDir
$lnk.Description = "HP LaserJet P1007 打印机控制：清除任务/急停/恢复打印"
if (Test-Path $iconFile) { $lnk.IconLocation = "$iconFile,0" }
$lnk.Save()
Write-Host "快捷方式已创建：$lnkPath"
