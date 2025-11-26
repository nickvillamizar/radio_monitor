#!/usr/bin/env python3
import subprocess
import sys

# Obtener la versión original del index.html
result = subprocess.run(
    ['git', 'show', '9e7ad7b:templates/index.html'],
    capture_output=True,
    text=True,
    cwd='c:\\Users\\57321\\OneDrive\\Escritorio\\radio_monitor-main\\radio_monitor-main'
)

if result.returncode != 0:
    print(f"Error: {result.stderr}")
    sys.exit(1)

content = result.stdout

# Encontrar la línea del header-actions y reemplazarla
old_header = '''      <div class="header-actions">
        <div class="small-muted">Intervalo: {{ config.MONITOR_INTERVAL }}s</div>
        <button id="refresh-btn" class="btn-outline">Actualizar ahora</button>
        <!-- NUEVO: Botón para ingresar canción manualmente -->
        <button id="manual-song-btn" class="btn-primary">🎵 Ingresar canción</button>
      </div>'''

new_header = '''      <div class="header-actions">
        <div id="sync-status" style="font-weight: bold; font-size: 0.9rem; display: flex; align-items: center; gap: 0.5rem; color: #00e8a2;">
          <span id="sync-dot" style="display: inline-block; width: 8px; height: 8px; background: #00e8a2; border-radius: 50%; animation: pulse 2s infinite;"></span>
          <span id="sync-text">Sincronizado</span>
          <span style="color: #888; font-size: 0.85rem;">(Próx: <span id="sync-countdown">15</span>s)</span>
        </div>
        <button id="refresh-btn" class="btn-outline">Actualizar ahora</button>
        <!-- NUEVO: Botón para ingresar canción manualmente -->
        <button id="manual-song-btn" class="btn-primary">🎵 Ingresar canción</button>
      </div>'''

# Reemplazar
content = content.replace(old_header, new_header)

# Guardar el archivo
with open('c:\\Users\\57321\\OneDrive\\Escritorio\\radio_monitor-main\\radio_monitor-main\\templates\\index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ index.html restaurado correctamente")
