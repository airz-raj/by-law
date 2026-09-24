import sys
import os
import traceback

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def safe_create_app():
    try:
        from app.main import create_app
        return create_app()
    except Exception as e:
        err_tb = traceback.format_exc()
        async def error_app(scope, receive, send):
            assert scope['type'] == 'http'
            await send({
                'type': 'http.response.start',
                'status': 500,
                'headers': [(b'content-type', b'text/plain')]
            })
            await send({
                'type': 'http.response.body',
                'body': f"Initialization Error:\n\n{err_tb}".encode('utf-8')
            })
        return error_app

app = safe_create_app()
