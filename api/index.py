import os
import sys
import urllib.parse

# Ensure the project root directory is on the Python module search path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app


class VercelWSGIRouteFix:
    """
    WSGI middleware to normalize PATH_INFO on Vercel.
    Vercel passes the original route via __vercel_route_path__ captured group.
    This restores the exact requested path (/register, /static/css/style.css, etc.)
    so Flask routes pages and serves CSS/JS static files with correct MIME types.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        query = environ.get('QUERY_STRING', '')
        if '__vercel_route_path__=' in query:
            params = urllib.parse.parse_qs(query, keep_blank_values=True)
            if '__vercel_route_path__' in params:
                route_path = params['__vercel_route_path__'][0]
                while route_path.startswith('//'):
                    route_path = route_path[1:]
                if not route_path or not route_path.startswith('/'):
                    route_path = '/' + route_path
                environ['PATH_INFO'] = route_path

                # Remove internal routing token from query string
                del params['__vercel_route_path__']
                environ['QUERY_STRING'] = urllib.parse.urlencode(params, doseq=True)

        return self.wsgi_app(environ, start_response)


# Apply the middleware wrapper
app.wsgi_app = VercelWSGIRouteFix(app.wsgi_app)
