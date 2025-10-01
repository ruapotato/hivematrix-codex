class PrefixMiddleware:
    """
    Middleware to handle URL prefixes when app is behind a reverse proxy.
    
    This allows Flask to work correctly when Nexus routes requests like:
    http://nexus:8000/codex/ -> http://codex:5010/
    """
    def __init__(self, app, prefix=''):
        self.app = app
        self.prefix = prefix

    def __call__(self, environ, start_response):
        if self.prefix:
            # Add the prefix to SCRIPT_NAME so Flask knows its base path
            script_name = environ.get('SCRIPT_NAME', '')
            if script_name.startswith(self.prefix):
                # Already has prefix, don't add again
                pass
            else:
                environ['SCRIPT_NAME'] = self.prefix + script_name
                
            # Adjust PATH_INFO to remove the prefix
            path_info = environ.get('PATH_INFO', '')
            if path_info.startswith(self.prefix):
                environ['PATH_INFO'] = path_info[len(self.prefix):]

        return self.app(environ, start_response)
