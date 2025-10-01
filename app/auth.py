from functools import wraps
from flask import request, g, current_app, abort
import jwt

# Cache for Core's public key
jwks_client = None

def init_jwks_client():
    """Initializes the JWKS client from the URL in config."""
    global jwks_client
    core_url = current_app.config.get('CORE_SERVICE_URL')
    if core_url:
        jwks_client = jwt.PyJWKClient(f"{core_url}/.well-known/jwks.json")

def token_required(f):
    """
    A decorator to protect routes, ensuring a valid JWT is present.
    This now accepts both user tokens and service tokens.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Initialize the JWKS client on the first request
        if jwks_client is None:
            init_jwks_client()

        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            abort(401, description="Authorization header is missing or invalid.")

        token = auth_header.split(' ')[1]

        try:
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            data = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                issuer="hivematrix.core",
                options={"verify_exp": True}
            )
            
            # Determine if this is a user token or service token
            if data.get('type') == 'service':
                # Service-to-service call
                g.user = None
                g.service = data.get('calling_service')
                g.is_service_call = True
            else:
                # User call
                g.user = data
                g.service = None
                g.is_service_call = False
                
        except jwt.PyJWTError as e:
            abort(401, description=f"Invalid Token: {e}")

        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin permission level."""
    @wraps(f)
    @token_required
    def decorated_function(*args, **kwargs):
        if g.is_service_call:
            # Services can access admin routes
            return f(*args, **kwargs)
        
        if not g.user or g.user.get('permission_level') != 'admin':
            abort(403, description="Admin access required.")
        
        return f(*args, **kwargs)
    return decorated_function
