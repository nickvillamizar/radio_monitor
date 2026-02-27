from app import app
from utils.stream_reader import get_real_stream_url, get_icy_metadata
from utils.db import db
from models.emisoras import Emisora
import requests

problem_ids = [228,46,43,39,37,35,34,30,27]
problem_names = [
    'Montonestv',
    'Radio CTC Moncion',
    'Lider 92.7',
    'La Kalle 96.3',
    'Turbo 98',
    'Sabrosa',
    'Mao'
]

with app.app_context():
    print('\nDIAGNOSTICO INICIADO\n')
    for pid in problem_ids:
        e = Emisora.query.get(pid)
        if e:
            print('--- ID', pid, e.nombre)
            url = e.url_stream or e.url
            print('  Config URL:', url)
            real = None
            if url:
                real = get_real_stream_url(url)
            print('  Resolved URL ->', real)
            # HEAD check
            if real:
                try:
                    r = requests.head(real, timeout=6, allow_redirects=True)
                    print('  HEAD', r.status_code, 'content-type=', r.headers.get('content-type'))
                except Exception as ex:
                    print('  HEAD ERROR', ex)
                # icy
                try:
                    icy = get_icy_metadata(real, timeout=6)
                    print('  ICY ->', icy)
                except Exception as ex:
                    print('  ICY ERROR', ex)
            else:
                print('  No URL para verificar')
        else:
            print('--- ID', pid, 'NO ENCONTRADA')

    # search by partial name for missing or 0 IDs
    print('\nBUSCAR POR NOMBRE\n')
    for name in problem_names:
        rows = Emisora.query.filter(Emisora.nombre.ilike(f'%{name}%')).all()
        if rows:
            for s in rows:
                print('FOUND:', s.id, s.nombre, '->', s.url_stream)
        else:
            print('NO FOUND for', name)

    print('\nDIAGNOSTICO FINALIZADO\n')
