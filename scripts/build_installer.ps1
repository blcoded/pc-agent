<#
.SYNOPSIS
    Builds the Inno Setup Windows installer for PC Voice Agent (TASK-8.4).

.DESCRIPTION
    Validates the installer.iss configuration, checks for the presence of the
    PyInstaller-built application directory, locates ISCC.exe (Inno Setup Compiler),
    and compiles the production-ready setup executable.

.PARAMETER IssFile
    Path to the Inno Setup script. Defaults to 'packaging\installer.iss'.

.PARAMETER IsccPath
    Explicit path to ISCC.exe. If omitted, standard locations and PATH are searched.

.PARAMETER DryRun
    Perform pre-flight validation without compiling.

.EXAMPLE
    .\scripts\build_installer.ps1 -DryRun
#>

[CmdletBinding()]
param(
    [string]$IssFile = "packaging\installer.iss",
    [string]$IsccPath = "",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "      PC Voice Agent - Windows Installer Builder  " -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

$RepoRoot = Split-Path -Parent $PSScriptRoot
$IssFullPath = Join-Path $RepoRoot $IssFile

Write-Host "Repository Root: $RepoRoot"
Write-Host "Inno Setup File: $IssFullPath"

# 1. Validate ISS file existence
if (-not (Test-Path $IssFullPath)) {
    Write-Error "[Installer] Error: Inno Setup script '$IssFullPath' does not exist."
    exit 1
}

# 2. Inspect ISS file contents
Write-Host "[Installer] Validating script structure..."
$IssContent = Get-Content $IssFullPath -Raw

$RequiredSections = @("[Setup]", "[Languages]", "[Tasks]", "[Files]", "[Icons]", "[Registry]", "[Run]")
foreach ($sec in $RequiredSections) {
    if (-not $IssContent.Contains($sec)) {
        Write-Error "[Installer] Error: Missing required Inno Setup section: $sec"
        exit 1
    }
}

$RequiredTokens = @("PCVoiceAgent.exe", "DefaultDirName", "OutputBaseFilename", "CloseApplications=yes")
foreach ($tok in $RequiredTokens) {
    if (-not $IssContent.Contains($tok)) {
        Write-Error "[Installer] Error: Missing required token: $tok"
        exit 1
    }
}
Write-Host "[Installer] Script structure validated successfully." -ForegroundColor Green

# 3. Check for built PyInstaller binaries
$DistFolder = Join-Path $RepoRoot "dist\PCVoiceAgent"
if (-not (Test-Path $DistFolder)) {
    Write-Host "[Installer] Warning: '$DistFolder' not found." -ForegroundColor Yellow
    Write-Host "[Installer] Note: Run 'python scripts\build.py' prior to building final installer." -ForegroundColor Yellow
} else {
    Write-Host "[Installer] Application binaries found in '$DistFolder'." -ForegroundColor Green
}

# 4. Handle DryRun
if ($DryRun) {
    Write-Host "`n[Installer] Dry run completed successfully. All pre-flight checks passed." -ForegroundColor Green
    exit 0
}

# 5. Locate ISCC.exe
$Candidates = @(
    $IsccPath,
    (Get-Command iscc.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source),
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 5\ISCC.exe"
)

$FoundIscc = $null
foreach ($cand in $Candidates) {
    if ($cand -and (Test-Path $cand)) {
        $FoundIscc = $cand
        break
    }
}

if (-not $FoundIscc) {
    Write-Host "`n[Installer] Notice: Inno Setup Compiler (ISCC.exe) not found on this system." -ForegroundColor Yellow
    Write-Host "[Installer] To compile the Windows installer executable, install Inno Setup 6:" -ForegroundColor Yellow
    Write-Host "    Download: https://jrsoftware.org/isdl.php" -ForegroundColor Yellow
    Write-Host "    Or via winget: winget install JRSoftware.InnoSetup" -ForegroundColor Yellow
    Write-Host "    Then compile with: iscc `"$IssFullPath`"" -ForegroundColor Yellow
    Write-Host "`n[Installer] Validation succeeded: packaging/installer.iss is ready for compilation." -ForegroundColor Green
    exit 0
}

Write-Host "[Installer] Found Inno Setup Compiler at: $FoundIscc" -ForegroundColor Green
Write-Host "[Installer] Compiling installer..."

& $FoundIscc $IssFullPath

if ($LASTEXITCODE -eq 0) {
    $OutputDir = Join-Path $RepoRoot "dist\installer"
    Write-Host "==================================================" -ForegroundColor Green
    Write-Host "[Installer] Setup build succeeded!" -ForegroundColor Green
    Write-Host "Output Directory: $OutputDir" -ForegroundColor Green
    Write-Host "==================================================" -ForegroundColor Green
    exit 0
} else {
    Write-Error "[Installer] Inno Setup compilation failed with exit code $LASTEXITCODE."
    exit $LASTEXITCODE
}
