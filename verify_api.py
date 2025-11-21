import json
import subprocess
import sys

try:
    # Usar curl con WSL o Windows native curl
    result = subprocess.run(
        ['powershell', '-Command', 
         '[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12; '
         '(Invoke-WebRequest -Uri "http://127.0.0.1:5000/api/emisoras" -UseBasicParsing).Content'],
        capture_output=True,
        text=True,
        timeout=10
    )
    
    if result.returncode != 0:
        print(f'Error: {result.stderr}')
    else:
        content = result.stdout.strip()
        if content:
            data = json.loads(content)
            print(f'✓ API retorna: {len(data)} emisoras')
            if len(data) > 0:
                print('\nPrimeras 3:')
                for e in data[:3]:
                    print(f'  - {e["nombre"]}: {e["estado"]} ({e.get("dias_sin_actualizar", "?")} dias)')
        else:
            print('Error: respuesta vacía')
except Exception as ex:
    print(f'✗ Error: {ex}')
    import traceback
    traceback.print_exc()

