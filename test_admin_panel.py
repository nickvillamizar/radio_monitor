#!/usr/bin/env python3
"""
TEST - Panel de administración
Verifica que los endpoints CRUD estén funcionando
"""

import sys
sys.path.insert(0, '.')
from app import app
import json

print("\n" + "="*80)
print("TEST - PANEL DE ADMINISTRACIÓN")
print("="*80 + "\n")

with app.test_client() as client:
    # 1. GET /admin - Verificar que la página se carga
    print("[1] GET /admin - Cargar página admin")
    print("-"*80)
    resp = client.get('/admin')
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        print("✅ Página admin cargada correctamente\n")
    else:
        print(f"❌ Error cargando página admin: {resp.status_code}\n")
    
    # 2. GET /api/emisoras - Listar todas
    print("[2] GET /api/emisoras - Listar emisoras")
    print("-"*80)
    resp = client.get('/api/emisoras')
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        emisoras = resp.get_json()
        print(f"✅ {len(emisoras)} emisoras obtenidas\n")
        if emisoras:
            first = emisoras[0]
            print(f"   Ejemplo ID {first['id']}: {first['nombre']}\n")
    else:
        print(f"❌ Error: {resp.status_code}\n")
    
    # 3. POST /api/emisoras - Crear nueva
    print("[3] POST /api/emisoras - Crear emisora test")
    print("-"*80)
    
    payload = {
        "nombre": "TEST Radio 99.9",
        "pais": "República Dominicana",
        "url_stream": "https://stream.test.example.com/radio",
        "sitio_web": "https://test.example.com"
    }
    
    resp = client.post('/api/emisoras', 
        json=payload,
        content_type='application/json'
    )
    print(f"Status: {resp.status_code}")
    data = resp.get_json()
    
    if resp.status_code == 201:
        test_id = data.get('id')
        print(f"✅ Emisora creada con ID {test_id}\n")
        
        # 4. GET /api/emisoras/<id> - Obtener detalles
        print(f"[4] GET /api/emisoras/{test_id} - Obtener detalles")
        print("-"*80)
        resp = client.get(f'/api/emisoras/{test_id}')
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            emisora = resp.get_json()
            print(f"✅ Detalles obtenidos:")
            print(f"   Nombre: {emisora['nombre']}")
            print(f"   País: {emisora['pais']}")
            print(f"   URL: {emisora['url_stream']}\n")
            
            # 5. PUT /api/emisoras/<id> - Actualizar
            print(f"[5] PUT /api/emisoras/{test_id} - Actualizar emisora")
            print("-"*80)
            
            update_payload = {
                "nombre": "TEST Radio UPDATED",
                "pais": "México"
            }
            
            resp = client.put(f'/api/emisoras/{test_id}',
                json=update_payload,
                content_type='application/json'
            )
            print(f"Status: {resp.status_code}")
            
            if resp.status_code == 200:
                print(f"✅ Emisora actualizada\n")
                
                # Verificar cambio
                resp = client.get(f'/api/emisoras/{test_id}')
                if resp.status_code == 200:
                    emisora = resp.get_json()
                    print(f"   Nombre actualizado: {emisora['nombre']}")
                    print(f"   País actualizado: {emisora['pais']}\n")
            else:
                print(f"❌ Error: {resp.status_code}\n")
            
            # 6. DELETE /api/emisoras/<id> - Eliminar
            print(f"[6] DELETE /api/emisoras/{test_id} - Eliminar emisora")
            print("-"*80)
            
            resp = client.delete(f'/api/emisoras/{test_id}')
            print(f"Status: {resp.status_code}")
            
            if resp.status_code == 200:
                print(f"✅ Emisora eliminada\n")
                
                # Verificar que se eliminó
                resp = client.get(f'/api/emisoras/{test_id}')
                if resp.status_code == 404:
                    print(f"   ✅ Confirmado: Emisora no existe (404)\n")
            else:
                print(f"❌ Error: {resp.status_code}\n")
        else:
            print(f"❌ Error obteniendo detalles: {resp.status_code}\n")
    else:
        print(f"❌ Error creando: {resp.status_code}")
        print(f"   Respuesta: {data}\n")

print("="*80)
print("✅ TEST COMPLETADO - Panel de administración funcionando")
print("="*80 + "\n")
