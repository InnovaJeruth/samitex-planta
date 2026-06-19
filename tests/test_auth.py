"""Tests para app/core/auth.py — funciones puras de hash y JWT."""
from app.core.auth import hash_password, verify_password, create_access_token, _decode_token


class TestPassword:
    def test_hash_returns_string(self):
        h = hash_password("mipassword")
        assert isinstance(h, str)
        assert len(h) > 0

    def test_hash_starts_with_bcrypt_prefix(self):
        h = hash_password("test")
        assert h.startswith("$2b$")

    def test_different_hashes_per_call(self):
        # bcrypt usa salt aleatorio → nunca idénticos
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2

    def test_verify_correct_password(self):
        h = hash_password("correcto123")
        assert verify_password("correcto123", h) is True

    def test_verify_wrong_password(self):
        h = hash_password("correcto123")
        assert verify_password("incorrecto", h) is False

    def test_verify_empty_password_against_hash(self):
        h = hash_password("nonempty")
        assert verify_password("", h) is False

    def test_verify_with_garbage_hash_returns_false(self):
        assert verify_password("password", "not-a-hash") is False


class TestJWT:
    def test_create_and_decode_roundtrip(self):
        token = create_access_token({"sub": "usuario1"})
        sub = _decode_token(token)
        assert sub == "usuario1"

    def test_decode_returns_none_for_garbage(self):
        assert _decode_token("esto.no.es.jwt") is None

    def test_decode_returns_none_for_empty_string(self):
        assert _decode_token("") is None

    def test_decode_returns_none_for_token_signed_with_wrong_key(self):
        from jose import jwt
        # Firmar con una clave diferente
        bad_token = jwt.encode({"sub": "hacker"}, "wrong-key", algorithm="HS256")
        assert _decode_token(bad_token) is None

    def test_token_payload_has_expiry(self):
        from jose import jwt
        from app.config import settings
        token = create_access_token({"sub": "test_user"})
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        assert "exp" in payload

    def test_decode_returns_correct_sub_for_different_users(self):
        for username in ["admin", "supervisor", "planeador"]:
            token = create_access_token({"sub": username})
            assert _decode_token(token) == username
