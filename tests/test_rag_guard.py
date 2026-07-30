"""R3 · RAG Text-to-SQL. Barreras de seguridad y ejecución read-only."""
import pytest
from sqlalchemy import text

from app.services import rag_guard as g
from app.services.rag_guard import SQLNoPermitido


# ── Rechazos (defensa contra escritura / abuso) ──────────────────────────────
@pytest.mark.parametrize("sql", [
    "DELETE FROM ordenes_fabricacion",
    "UPDATE ordenes_fabricacion SET estado='X'",
    "INSERT INTO ordenes_fabricacion (id) VALUES (1)",
    "DROP TABLE ordenes_fabricacion",
    "SELECT * INTO copia FROM ordenes_fabricacion",           # SELECT INTO escribe
    "EXEC sp_who",
    "SELECT * FROM ordenes_fabricacion; DROP TABLE usuarios",  # 2 sentencias
    "SELECT * FROM ordenes_fabricacion -- comentario",         # comentario
    "SELECT id FROM tokens_revocados",                         # tabla fuera del whitelist
    "SELECT id FROM sys.objects",                              # tabla de sistema
    # ── P0: fuga de credenciales / PII ──────────────────────────────
    "SELECT id, nombre FROM usuarios",                         # tabla usuarios ya NO está en whitelist
    "SELECT password_hash FROM vw_usuarios",                   # columna sensible bloqueada
    "SELECT id, token FROM ordenes_fabricacion",               # columna sensible bloqueada
    "SELECT * FROM vw_usuarios",                               # SELECT * prohibido
    "SELECT u.* FROM vw_usuarios u",                           # alias.* prohibido
    "SELECT TOP 200 * FROM ordenes_fabricacion",               # SELECT * con TOP prohibido
])
def test_validar_rechaza(sql):
    with pytest.raises(SQLNoPermitido):
        g.validar_sql(sql)


# ── Aceptación de la vista segura de usuarios (quién hizo X) ─────────────────
def test_permite_vw_usuarios_columnas_seguras():
    g.validar_sql("SELECT id, nombre, username, rol FROM vw_usuarios")


def test_count_star_permitido():
    # COUNT(*) no es SELECT * → debe pasar
    g.validar_sql("SELECT COUNT(*) AS n FROM ordenes_fabricacion")


# ── Aceptación + saneo ───────────────────────────────────────────────────────
def test_inyecta_top_si_falta():
    out = g.inyectar_top("SELECT numero_of FROM ordenes_fabricacion", 50)
    assert out.upper().startswith("SELECT TOP 50")


def test_respeta_top_existente():
    out = g.inyectar_top("SELECT TOP 5 numero_of FROM ordenes_fabricacion", 50)
    assert out.upper().count("TOP") == 1


def test_no_inyecta_top_en_with():
    out = g.inyectar_top("WITH x AS (SELECT id FROM ordenes_fabricacion) SELECT * FROM x", 50)
    assert "TOP" not in out.upper()


def test_permite_join_y_cte():
    g.validar_sql("SELECT o.numero_of, p.nombre FROM ordenes_fabricacion o "
                  "JOIN prendas_catalogo p ON p.id = o.prenda_catalogo_id")
    # el CTE 'x' no se considera tabla externa (columnas explícitas)
    assert g.validar_sql("WITH x AS (SELECT id FROM ordenes_fabricacion) SELECT id FROM x")


# ── Ejecución real (sqlite del fixture db) ───────────────────────────────────
def test_ejecutar_solo_lectura(db):
    r = g.ejecutar("SELECT COUNT(*) AS n FROM ordenes_fabricacion", db, max_rows=10)
    assert r["columnas"] == ["n"]
    assert r["filas"] == [{"n": 0}]
    assert r["sql"].strip().upper().startswith("SELECT")   # COUNT no lleva TOP forzado


def test_ejecutar_rechaza_escritura(db):
    with pytest.raises(SQLNoPermitido):
        g.ejecutar("DELETE FROM ordenes_fabricacion", db)


def test_fmt_valor_fechas_legibles():
    from datetime import datetime, date
    from decimal import Decimal
    assert g._fmt_valor(datetime(2026, 7, 20, 8, 32, 23, 893000)) == "2026-07-20 08:32:23"
    assert g._fmt_valor(datetime(2026, 7, 20, 0, 0, 0)) == "2026-07-20"   # sin hora → solo fecha
    assert g._fmt_valor(date(2026, 7, 20)) == "2026-07-20"
    assert g._fmt_valor(Decimal("3.50")) == 3.5
    assert g._fmt_valor("texto") == "texto"


def test_ejecutar_cap_filas(db):
    # inserta 3 motivos (vía ORM para respetar defaults) y pide tope de 2
    from app.models.paquete import MotivoRechazo
    for c in ("C1", "C2", "C3"):
        db.add(MotivoRechazo(codigo=c, descripcion=c, activo=True))
    db.commit()
    r = g.ejecutar("SELECT codigo FROM motivos_rechazo", db, max_rows=2)
    assert len(r["filas"]) == 2
