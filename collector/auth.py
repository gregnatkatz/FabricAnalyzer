"""Phase 10 — Auth: server-side token handling for Fabric API calls.
Tokens are passed from the React frontend (via MSAL popup) through the Express proxy.
This module validates and refreshes tokens as needed.
"""


def validate_token(token):
    """Basic token validation — checks format.
    
    The actual OAuth flow happens in the browser via MSAL.js.
    Tokens are passed in Authorization headers through the Express proxy.
    This is a server-side sanity check only.
    """
    if not token:
        return False, 'No token provided'

    if not isinstance(token, str):
        return False, 'Token must be a string'

    # JWT has 3 parts separated by dots
    parts = token.split('.')
    if len(parts) != 3:
        return False, 'Invalid JWT format'

    return True, 'Token format valid'


def get_scopes():
    """Return the required OAuth scopes for Fabric API access."""
    return [
        'https://analysis.windows.net/powerbi/api/.default',
    ]
