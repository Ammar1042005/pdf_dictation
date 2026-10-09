param(
    [switch]$Install
)

$ErrorActionPreference = "Stop"

function Find-Tesseract {
    $command = Get-Command tesseract -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $candidates = @(
        "$env:ProgramFiles\Tesseract-OCR\tesseract.exe",
        "${env:ProgramFiles(x86)}\Tesseract-OCR\tesseract.exe"
    )
    return $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}

$tesseract = Find-Tesseract
if ($tesseract) {
    Write-Host "Tesseract is already installed: $tesseract"
    & $tesseract --version | Select-Object -First 1
    exit 0
}

if (-not $Install) {
    Write-Host "Tesseract OCR is not installed."
    Write-Host "Re-run with -Install to use WinGet, or install Tesseract manually."
    Write-Host "The application remains fully usable for PDFs with a text layer."
    exit 1
}

if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    throw "WinGet is unavailable. Install Tesseract manually from the UB Mannheim Windows distribution."
}

winget install --id UB Mannheim.TesseractOCR -e --accept-package-agreements --accept-source-agreements
if ($LASTEXITCODE -ne 0) {
    throw "WinGet could not install Tesseract (exit code $LASTEXITCODE)."
}

Write-Host "Tesseract installation finished. Restart PDF Dictation before enabling OCR."
