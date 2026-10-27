# 从 HP 官方分发服务器下载 LaserJet P1000-P1500 驱动安装包并校验。
# 本脚本不镜像、不附带 HP 软件；下载的安装包归 HP EULA 约束，仅供个人在本机安装使用。
#
# 用法（PowerShell，无需管理员）：
#   .\scripts\get-driver.ps1                 # 下载到 .\downloads\
#   .\scripts\get-driver.ps1 -Install        # 下载后弹出 UAC 并静默安装（pnputil）
#
# 安装包内含 64 位驱动；32 位系统请改用官方 32 位包（自行核对下方 URL 的 win32 路径）。

param(
    [switch]$Install,
    [string]$DestDir = (Join-Path $PSScriptRoot "..\downloads")
)

$ErrorActionPreference = "Stop"

# HP 官方 CDN 直链（来自 support.hp.com 产品页 3435678 所指向的官方分发服务器）
$Url  = "https://ftp.hp.com/pub/softlib/software12/COL21058/bi-55362-7/ljP1000_P1500-HB-pnp-win64-en.exe"
$Mirror = "https://ftp.ext.hp.com/pub/softlib/software12/COL21058/bi-55362-7/ljP1000_P1500-HB-pnp-win64-en.exe"
# SHA256 实测值（下载后请自行复核：Get-FileHash <file> -Algorithm SHA256）
$ExpectSha256 = "36F023ACFE5DC18ABE5C7FA5341E8DCFC369DF1A60BA9832C822D624FDDFA527"
$Size = 4011640

New-Item -ItemType Directory -Force -Path $DestDir | Out-Null
$Out = Join-Path $DestDir "ljP1000_P1500-HB-pnp-win64-en.exe"

if (Test-Path $Out) {
    $h = (Get-FileHash $Out -Algorithm SHA256).Hash
    if ($h -eq $ExpectSha256) {
        Write-Host "已存在且校验通过：$Out"
        $downloaded = $true
    } else {
        Write-Warning "已存在但校验不符，将重新下载：$Out"
        Remove-Item $Out -Force
        $downloaded = $false
    }
} else {
    $downloaded = $false
}

if (-not $downloaded) {
    Write-Host "从 HP 官方服务器下载（约 3.8 MB）..."
    $ok = $false
    foreach ($u in @($Url, $Mirror)) {
        try {
            # BITS 对不稳定网络更可靠，支持断点续传
            Start-BitsTransfer -Source $u -Destination $Out -ErrorAction Stop
            $ok = $true
            break
        } catch {
            Write-Warning "BITS 失败（$u）：$($_.Exception.Message)；尝试 Invoke-WebRequest..."
            try {
                Invoke-WebRequest -Uri $u -OutFile $Out -UseBasicParsing -ErrorAction Stop
                $ok = $true
                break
            } catch {
                Write-Warning "Invoke-WebRequest 也失败（$u）：$($_.Exception.Message)"
            }
        }
    }
    if (-not $ok) { throw "下载失败：请检查网络后重试，或手动从 support.hp.com 搜索 P1007 下载。" }
}

# 校验 1：SHA256
$hash = (Get-FileHash $Out -Algorithm SHA256).Hash
if ($hash -ne $ExpectSha256) {
    Remove-Item $Out -Force
    throw "SHA256 校验失败（得到 $hash），已删除可疑文件。请重新运行本脚本。"
}
$fi = Get-Item $Out
if ($fi.Length -ne $Size) { throw "文件大小异常（$($fi.Length) B，期望 $Size B）。" }

# 校验 2：Authenticode 数字签名必须为 Valid 且签名者是 HP
$sig = Get-AuthenticodeSignature $Out
if ($sig.Status -ne "Valid" -or $sig.SignerCertificate.Subject -notmatch "Hewlett-Packard") {
    Remove-Item $Out -Force
    throw "数字签名校验失败（$($sig.Status)），已删除可疑文件。"
}

Write-Host "校验通过：SHA256 与 HP 数字签名均正确：$Out"

if ($Install) {
    if (-not (Test-Path "$env:SystemRoot\System32\pnputil.exe")) { throw "未找到 pnputil.exe（需要 Windows）。" }
    Write-Host "解包中..."
    $tmp = Join-Path $env:TEMP ("hp1007_" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $tmp | Out-Null
    # 包体是 WinZip 风格自解压 + 7z 载荷；用系统 tar 不行，改用 7z 若可用，否则提示用户手动双击
    $7z = Get-Command 7z -ErrorAction SilentlyContinue
    if (-not $7z) {
        $7zExe = "C:\Program Files\7-Zip\7z.exe"
    } else { $7zExe = $7z.Source }
    if (-not (Test-Path $7zExe)) {
        Write-Host "未检测到 7-Zip，请直接双击运行 $Out，按安装向导完成（打印机插上 USB 后自动识别）。"
        exit 0
    }
    & $7zExe x $Out ("-o" + $tmp) drv64.cab HPLJP1005.INF hp100664.cat -y | Out-Null
    & $7zExe x (Join-Path $tmp "drv64.cab") ("-o" + (Join-Path $tmp "drv64")) -y | Out-Null
    # 组装 INF 安装树并预置驱动（需要管理员）
    $root = Join-Path $tmp "root"
    New-Item -ItemType Directory -Path (Join-Path $root "English\x64") -Force | Out-Null
    & $7zExe x $Out ("-o" + $root) -y | Out-Null
    Copy-Item (Join-Path $tmp "drv64\*") $root -Force
    Copy-Item (Join-Path $root "English\*.*") (Join-Path $root "English") -ErrorAction SilentlyContinue
    Copy-Item (Join-Path $root "English\x64\hp1006SMs.dll") (Join-Path $root "English\x64") -ErrorAction SilentlyContinue
    Copy-Item $root -Destination (Join-Path $root "SChinese") -Recurse -Force   # 中文系统语言目录兜底
    Copy-Item (Join-Path $tmp "drv64.cab") $root -Force

    $cmd = Join-Path $tmp "install.cmd"
    @"
@echo off
pnputil /add-driver "$root\HPLJP1005.INF" /install
exit /b %ERRORLEVEL%
"@ | Set-Content -Path $cmd -Encoding ASCII

    Write-Host "以管理员权限安装（请在 UAC 弹窗点“是”）..."
    $p = Start-Process cmd.exe -ArgumentList "/c", $cmd -Verb RunAs -Wait -PassThru -WindowStyle Hidden
    if ($p.ExitCode -eq 0) {
        Write-Host "安装完成。插入打印机 USB 线即可自动识别（或已在队列中直接可用）。"
    } else {
        Write-Warning "pnputil 返回 $($p.ExitCode)，请检查输出。"
    }
}
