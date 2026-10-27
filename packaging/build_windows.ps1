# Build script for PDF Dictation Windows executable
# This script creates a protected single-file exe with PyArmor and PyInstaller

param(
    [switch]$Protect = $true,
    [switch]$SkipPyArmor = $false
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$DistDir = Join-Path $ProjectRoot "dist"

Write-Host "=== PDF Dictation Windows Build Script ===" -ForegroundColor Cyan
Write-Host "Project Root: $ProjectRoot" -ForegroundColor Gray
Write-Host ""

# Clean previous builds
Write-Host "Cleaning previous builds..." -ForegroundColor Yellow
if (Test-Path $DistDir) {
    try {
        Remove-Item -Recurse -Force $DistDir
    } catch {
        Write-Host "Could not clean dist directory (file may be in use). Continuing..." -ForegroundColor Yellow
    }
}
if (Test-Path (Join-Path $ProjectRoot "build")) {
    try {
        Remove-Item -Recurse -Force (Join-Path $ProjectRoot "build")
    } catch {
        Write-Host "Could not clean build directory (file may be in use). Continuing..." -ForegroundColor Yellow
    }
}

# Check if PyArmor is installed and protection is requested
if ($Protect -and -not $SkipPyArmor) {
    Write-Host "Checking for PyArmor..." -ForegroundColor Yellow
    try {
        $pyarmorVersion = pyarmor --version 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "PyArmor found: $pyarmorVersion" -ForegroundColor Green
        } else {
            throw "PyArmor not found"
        }
    } catch {
        Write-Host "PyArmor not found. Installing..." -ForegroundColor Yellow
        pip install pyarmor
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Failed to install PyArmor. Building without protection..." -ForegroundColor Yellow
            $Protect = $false
        }
    }
}

# Obfuscate code with PyArmor if requested
if ($Protect -and -not $SkipPyArmor) {
    Write-Host "Obfuscating code with PyArmor..." -ForegroundColor Yellow
    Push-Location $ProjectRoot
    
    # Backup original package
    if (Test-Path "pdf_dictation_original") {
        Remove-Item -Recurse -Force "pdf_dictation_original"
    }
    Copy-Item -Recurse "pdf_dictation" "pdf_dictation_original"
    
    try {
        # Obfuscate the package
        pyarmor gen --recursive --output pdf_dictation_protected pdf_dictation
        if ($LASTEXITCODE -eq 0) {
            # Replace original with protected version
            Remove-Item -Recurse -Force "pdf_dictation"
            Move-Item "pdf_dictation_protected" "pdf_dictation"
            Write-Host "Code obfuscation completed successfully" -ForegroundColor Green
        } else {
            throw "PyArmor obfuscation failed"
        }
    } catch {
        Write-Host "PyArmor obfuscation failed. Restoring original code..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force "pdf_dictation" -ErrorAction SilentlyContinue
        Move-Item "pdf_dictation_original" "pdf_dictation"
        $Protect = $false
    }
    
    Pop-Location
}

# Build with PyInstaller
Write-Host "Building executable with PyInstaller..." -ForegroundColor Yellow
Push-Location $ProjectRoot
pyinstaller --noconfirm packaging/pdfdictation.spec
if ($LASTEXITCODE -ne 0) {
    Write-Host "PyInstaller build failed!" -ForegroundColor Red
    exit 1
}
Pop-Location

# Restore original code if it was obfuscated
if ($Protect -and -not $SkipPyArmor -and (Test-Path (Join-Path $ProjectRoot "pdf_dictation_original"))) {
    Write-Host "Restoring original source code..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force (Join-Path $ProjectRoot "pdf_dictation")
    Move-Item (Join-Path $ProjectRoot "pdf_dictation_original") (Join-Path $ProjectRoot "pdf_dictation")
}

# Check if exe was created
$ExePath = Join-Path $DistDir "PDFDictation.exe"
if (Test-Path $ExePath) {
    $ExeSize = (Get-Item $ExePath).Length / 1MB
    Write-Host ""
    Write-Host "=== Build Successful ===" -ForegroundColor Green
    Write-Host "Executable: $ExePath" -ForegroundColor Cyan
    Write-Host "Size: $([math]::Round($ExeSize, 2)) MB" -ForegroundColor Cyan
    if ($Protect) {
        Write-Host "Protection: Enabled (PyArmor)" -ForegroundColor Green
    } else {
        Write-Host "Protection: Disabled" -ForegroundColor Yellow
    }
    Write-Host ""
    Write-Host "To create an installer, run:" -ForegroundColor Gray
    Write-Host "  iscc packaging/installer.iss" -ForegroundColor Gray
} else {
    Write-Host "Build failed - executable not found!" -ForegroundColor Red
    exit 1
}
