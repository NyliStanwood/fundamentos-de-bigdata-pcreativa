#!/usr/bin/env powershell
# Pre-compose line ending fixer for Windows developers
# Run this before docker-compose up to ensure shell scripts have Unix line endings

param(
    [string]$Path = "."
)

$shellFiles = Get-ChildItem -Path $Path -Filter "*.sh" -Recurse
$dockerFiles = Get-ChildItem -Path $Path -Filter "Dockerfile*" -Recurse

$allFiles = @($shellFiles) + @($dockerFiles)

if ($allFiles.Count -eq 0) {
    Write-Host "No shell or Docker files found."
    exit 0
}

Write-Host "Found $($allFiles.Count) files to check..."

$fixedCount = 0
foreach ($file in $allFiles) {
    $content = Get-Content -Path $file.FullName -Raw -Encoding UTF8
    
    # Check if file has CRLF line endings
    if ($content -match "`r`n") {
        Write-Host "Converting line endings: $($file.Name)"
        $fixed = $content -replace "`r`n", "`n"
        # Remove final newline to write cleanly
        $fixed = $fixed -replace "`n$", ""
        Set-Content -Path $file.FullName -Value $fixed -Encoding UTF8 -NoNewline
        Add-Content -Path $file.FullName -Value "`n" -Encoding UTF8 -NoNewline
        $fixedCount++
    }
}

Write-Host "Fixed $fixedCount files with Unix line endings (LF)"
