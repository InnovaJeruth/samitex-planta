"""Tests para app/core/csrf.py — funciones puras, sin DB."""
import pytest
from app.core.csrf import new_token, sign_token, verify_signed, is_exempt, CSRF_UNSAFE_METHODS

SECRET = "test-secret-key-samitex-tests"


class TestNewToken:
    def test_returns_hex_string(self):
        token = new_token()
        assert isinstance(token, str)
        int(token, 16)  # debe ser hex válido

    def test_length_is_64_chars(self):
        # secrets.token_hex(32) → 64 chars
        assert len(new_token()) == 64

    def test_generates_unique_tokens(self):
        tokens = {new_token() for _ in range(100)}
        assert len(tokens) == 100  # sin colisiones en 100 generaciones


class TestSignVerify:
    def test_roundtrip(self):
        token = new_token()
        signed = sign_token(token, SECRET)
        assert verify_signed(signed, SECRET) == token

    def test_tampered_token_rejected(self):
        token = new_token()
        signed = sign_token(token, SECRET)
        # Cambiar un carácter del token
        bad_signed = "x" + signed[1:]
        assert verify_signed(bad_signed, SECRET) is None

    def test_tampered_signature_rejected(self):
        token = new_token()
        signed = sign_token(token, SECRET)
        # Corromper la firma (parte después del punto)
        parts = signed.rsplit(".", 1)
        bad_signed = parts[0] + ".deadbeef"
        assert verify_signed(bad_signed, SECRET) is None

    def test_wrong_secret_rejected(self):
        token = new_token()
        signed = sign_token(token, SECRET)
        assert verify_signed(signed, "otro-secret") is None

    def test_empty_string_returns_none(self):
        assert verify_signed("", SECRET) is None

    def test_no_dot_returns_none(self):
        assert verify_signed("sinpunto", SECRET) is None

    def test_signed_value_contains_dot(self):
        signed = sign_token(new_token(), SECRET)
        assert "." in signed


class TestIsExempt:
    def test_get_always_exempt(self):
        assert is_exempt("/cualquier/ruta", "GET") is True

    def test_head_always_exempt(self):
        assert is_exempt("/ruta", "HEAD") is True

    def test_options_always_exempt(self):
        assert is_exempt("/ruta", "OPTIONS") is True

    def test_post_to_login_exempt(self):
        assert is_exempt("/auth/login", "POST") is True

    def test_post_to_health_exempt(self):
        assert is_exempt("/health", "POST") is True

    def test_post_to_telegram_webhook_exempt(self):
        assert is_exempt("/telegram/webhook", "POST") is True

    def test_post_to_ws_exempt(self):
        assert is_exempt("/ws/corte/42", "POST") is True

    def test_post_to_normal_route_not_exempt(self):
        assert is_exempt("/of/crear", "POST") is False

    def test_put_to_normal_route_not_exempt(self):
        assert is_exempt("/corte/1/registrar", "PUT") is False

    def test_delete_to_normal_route_not_exempt(self):
        assert is_exempt("/of/5", "DELETE") is False

    def test_patch_to_normal_route_not_exempt(self):
        assert is_exempt("/of/api/1/planificar", "PATCH") is False

    @pytest.mark.parametrize("method", list(CSRF_UNSAFE_METHODS))
    def test_all_unsafe_methods_on_protected_route(self, method):
        assert is_exempt("/corte/registrar", method) is False
