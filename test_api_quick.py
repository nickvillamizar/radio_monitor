import requests
import json

try:
    r = requests.get('http://127.0.0.1:5000/api/emisoras', timeout=5)
    data = r.json()
    print(f'Total: {len(data)}')
    if len(data) > 0:
        for e in data[:3]:
            print(f'  - {e["nombre"]}: {e["estado"]} ({e["dias_sin_actualizar"]} dias)')
    else:
        print('API retorno lista vacia')
except Exception as ex:
    print(f'Error: {ex}')
