# PowerShell equivalent of download_data.sh for Windows

# Get the script directory
$scriptDir = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition

# Navigate to data directory and download data files
$dataDir = Join-Path -Path $scriptDir -ChildPath ".." -AdditionalChildPath "data"
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
Set-Location $dataDir

Write-Host "Downloading flight delay features..."
curl.exe -L -o "simple_flight_delay_features.jsonl.bz2" "http://s3.amazonaws.com/agile_data_science/simple_flight_delay_features.jsonl.bz2"

Write-Host "Downloading origin-destination distances..."
curl.exe -L -o "origin_dest_distances.jsonl" "http://s3.amazonaws.com/agile_data_science/origin_dest_distances.jsonl"

# Create models directory and download models
$modelsDir = Join-Path -Path $scriptDir -ChildPath ".." -AdditionalChildPath "models"
New-Item -ItemType Directory -Force -Path $modelsDir | Out-Null

Write-Host "Downloading sklearn vectorizer model..."
curl.exe -L -o (Join-Path -Path $modelsDir -ChildPath "sklearn_vectorizer.pkl") "http://s3.amazonaws.com/agile_data_science/sklearn_vectorizer.pkl"

Write-Host "Downloading sklearn regressor model..."
curl.exe -L -o (Join-Path -Path $modelsDir -ChildPath "sklearn_regressor.pkl") "http://s3.amazonaws.com/agile_data_science/sklearn_regressor.pkl"

Write-Host "Download complete!"
