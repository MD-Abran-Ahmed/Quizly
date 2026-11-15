import os
import sys

# Ensure the project root directory is on the Python module search path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app


class VercelWSGIRouteFix:
    """
    WSGI middleware to normalize PATH_INFO on Vercel.
    When Vercel uses rewrites (/(.*) -> /api/index), Vercel's edge proxy routes
    the request to api/index.py and sets PATH_INFO to '/api/index' while storing
    the actual requested URL in HTTP headers like 'x-matched-path' or 'x-forwarded-uri'.
    This middleware restores the original requested path into PATH_INFO so Flask routes properly.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        raw_path = environ.get('PATH_INFO', '')

        # Check for original requested path passed by Vercel edge proxy
        matched = (
            environ.get('HTTP_X_MATCHED_PATH') or
            environ.get('HTTP_X_VERCEL_MATCHED_PATH') or
            environ.get('HTTP_X_FORWARDED_URI') or
            environ.get('HTTP_X_ORIGINAL_URL') or
            environ.get('HTTP_X_REWRITE_URL')
        )

        if matched:
            environ['PATH_INFO'] = matched.split('?')[0]
        elif raw_path in ('/api/index', '/api/index.py', '/api', '/api/'):
            environ['PATH_INFO'] = '/'

        return self.wsgi_app(environ, start_response)


# Apply the middleware wrapper
app.wsgi_app = VercelWSGIRouteFix(app.wsgi_app)
