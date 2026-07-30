"""
Protección CSRF — patrón Double-Submit Cookie.

Cómo funciona:
  1. El middleware genera un token aleatorio y lo guarda en una cookie
     (SameSite=Lax, NO HttpOnly → JS puede leerla).
  2. El JS del frontend lee la cookie y la envía como header X-CSRF-Token
     en todos los fetch() con métodos mutantes (POST/PUT/PATCH/DELETE).
  3. El middleware compara header vs cookie en cada request mutante.
     Si no coinciden → 403.

Rutas exentas (no requieren validación):
  - Métodos seguros: GET, HEAD, OPTIONS
  - /auth/login  (no hay cookie aún; CSRF en login es bajo riesgo)
  - /ws/  (WebSocket; no usa HTTP headers de la misma forma)
  - /health  (sólo lectura)
"""
import secrets
import hmac
import hashlib

CSRF_COOKIE = "csrftoken"
CSRF_HEADER = "x-csrf-token"

# Métodos que modifican estado
CSRF_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Rutas exentas (exactas o prefijos)
CSRF_EXEMPT_EXACT   = {"/auth/login", "/health"}
CSRF_EXEMPT_PREFIX  = ("/ws/",)


def new_token() -> str:
    """Genera un token CSRF aleatorio criptográficamente seguro."""
    return secrets.token_hex(32)


def sign_token(token: str, secret_key: str) -> str:
    """Devuelve token.hmac para detectar cookies manipuladas."""
    sig = hmac.new(secret_key.encode(), token.encode(), hashlib.sha256).hexdigest()
    return f"{token}.{sig}"


def verify_signed(signed: str, secret_key: str) -> str | None:
    """Valida la firma y devuelve el token puro, o None si es inválido."""
    try:
        token, sig = signed.rsplit(".", 1)
    except ValueError:
        return None
    expected = hmac.new(secret_key.encode(), token.encode(), hashlib.sha256).hexdigest()
    if hmac.compare_digest(sig, expected):
        return token
    return None


def is_exempt(path: str, method: str) -> bool:
    if method.upper() not in CSRF_UNSAFE_METHODS:
        return True
    if path in CSRF_EXEMPT_EXACT:
        return True
    return any(path.startswith(p) for p in CSRF_EXEMPT_PREFIX)
