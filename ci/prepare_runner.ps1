# Prepares a GitHub-hosted windows-2022 runner for a Supermium build stage:
# checks the toolchain and picks the work directory. The D: drive of these
# runners has about 220 GB free, which is enough without any cleanup.
$ErrorActionPreference = 'Continue'
"SM_JOB_START=$([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())" >> $env:GITHUB_ENV

function Show-Drives($title) {
  Write-Host "== $title"
  Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Used -ne $null } |
    Format-Table Name, @{n='FreeGB'; e={[math]::Round($_.Free / 1GB, 1)}},
                       @{n='UsedGB'; e={[math]::Round($_.Used / 1GB, 1)}} | Out-String | Write-Host
}

Show-Drives 'Drives'

# Chromium's checkout needs these; the runner's system git converts line endings.
git config --global core.autocrlf false
git config --global core.filemode false
git config --global core.longpaths true
git config --global core.fscache true
git config --global core.preloadindex true

# Real-time scanning slows down checkout and compilation a lot.
try { Set-MpPreference -DisableRealtimeMonitoring $true -ErrorAction Stop } catch { Write-Host "Defender: $_" }

# Chromium 150 needs Windows SDK 10.0.26100.0 with the Debugging Tools.
$kits = 'C:\Program Files (x86)\Windows Kits\10'
$sdkOk = (Test-Path "$kits\Include\10.0.26100.0\um\windows.h") -and (Test-Path "$kits\Debuggers\x64\dbghelp.dll")
if (-not $sdkOk) {
  Write-Host 'Installing Windows SDK 10.0.26100'
  $installer = "$env:RUNNER_TEMP\winsdksetup.exe"
  Invoke-WebRequest -Uri 'https://go.microsoft.com/fwlink/?linkid=2317808' -OutFile $installer
  $features = '/features OptionId.DesktopCPPx64 OptionId.DesktopCPPx86 OptionId.WindowsDesktopDebuggers OptionId.SigningTools /q /norestart /ceip off'
  $proc = Start-Process -FilePath $installer -ArgumentList $features -PassThru -Wait
  if ($proc.ExitCode -ne 0) { throw "winsdksetup.exe failed with code $($proc.ExitCode)" }
}
Get-ChildItem "$kits\Include" | ForEach-Object { Write-Host "SDK include: $($_.Name)" }

$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
$vs = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
Write-Host "Visual Studio: $vs"
Get-ChildItem "$vs\VC\Tools\MSVC" | ForEach-Object {
  Write-Host ("MSVC {0}, ATL: {1}" -f $_.Name, (Test-Path "$($_.FullName)\atlmfc\include\atlbase.h"))
}

# Work on the drive with the most free space, at a short path.
$best = Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Name -in @('C', 'D') -and $_.Free } |
  Sort-Object Free -Descending | Select-Object -First 1
$root = "$($best.Name):\sm"
New-Item -ItemType Directory -Force -Path $root | Out-Null
try { Add-MpPreference -ExclusionPath $root -ErrorAction Stop } catch { }
"SM_ROOT=$root" >> $env:GITHUB_ENV
Write-Host "Work directory: $root"
