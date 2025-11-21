$ErrorActionPreference = 'Continue'

Write-Host "Intentando conectar a http://127.0.0.1:5000/api/emisoras..." -ForegroundColor Cyan

try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:5000/api/emisoras" `
        -UseBasicParsing `
        -TimeoutSec 10
    
    Write-Host "Status: $($response.StatusCode)" -ForegroundColor Green
    Write-Host "Content Type: $($response.Headers['Content-Type'])"
    
    if ($response.Content.Length -lt 1000) {
        Write-Host "Content: $($response.Content)"
    } else {
        Write-Host "Content preview (first 500 chars):"
        Write-Host $response.Content.Substring(0, 500)
    }
    
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
}
