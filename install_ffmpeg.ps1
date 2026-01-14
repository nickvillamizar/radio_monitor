# Script para descargar e instalar ffmpeg en Windows (sin Chocolatey)
# Ejecutar en PowerShell como Administrador

$FFmpegUrl = "https://github.com/GyanD/codexffmpeg/releases/download/6.0/ffmpeg-6.0-full_build.7z"
$InstallPath = "C:\ffmpeg"
$DownloadPath = "$env:TEMP\ffmpeg.7z"

Write-Host "Descargando ffmpeg..." -ForegroundColor Cyan

# Descargar
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $FFmpegUrl -OutFile $DownloadPath -UseBasicParsing
    Write-Host "✓ Descargado correctamente" -ForegroundColor Green
} catch {
    Write-Host "✗ Error descargando: $_" -ForegroundColor Red
    exit 1
}

# Extraer (requiere 7-Zip o winrar)
Write-Host "Extrayendo..." -ForegroundColor Cyan

# Intentar con 7z si está instalado
$7zPath = "C:\Program Files\7-Zip\7z.exe"
if (Test-Path $7zPath) {
    & $7zPath x $DownloadPath -o"$InstallPath" -y | Out-Null
} else {
    # Fallback: usar Expand-Archive (solo .zip, pero lo convertimos)
    Write-Host "7-Zip no encontrado. Intenta descargar versión .zip en su lugar." -ForegroundColor Yellow
    Write-Host "Descarga manual desde: https://www.gyan.dev/ffmpeg/builds/" -ForegroundColor Yellow
    exit 1
}

Write-Host "✓ Extraído en $InstallPath" -ForegroundColor Green

# Añadir a PATH del sistema
$CurrentPath = [Environment]::GetEnvironmentVariable("PATH", [EnvironmentVariableTarget]::Machine)
if ($CurrentPath -notlike "*$InstallPath*") {
    $NewPath = "$CurrentPath;$InstallPath\bin"
    [Environment]::SetEnvironmentVariable("PATH", $NewPath, [EnvironmentVariableTarget]::Machine)
    Write-Host "✓ Añadido $InstallPath\bin al PATH del sistema" -ForegroundColor Green
} else {
    Write-Host "✓ Ya estaba en PATH" -ForegroundColor Green
}

# Verificar instalación
Write-Host "`nVerificando..." -ForegroundColor Cyan
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
ffmpeg -version

Write-Host "`n✓ ffmpeg instalado correctamente" -ForegroundColor Green
Write-Host "Cierra PowerShell y vuelve a abrir para que PATH se recargue." -ForegroundColor Yellow
