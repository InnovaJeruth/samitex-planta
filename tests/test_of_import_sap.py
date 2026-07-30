"""
Import de OF desde el Excel de SAP (COIS).
SQLite en memoria (fixture `db` de conftest.py).
"""
from datetime import datetime, date, time
from io import BytesIO

import openpyxl
import pytest

from app.models.of import OrdenFabricacion, EstadoOF, TipoClienteEnum
from app.models.catalogo import PrendaCatalogo, PrendaSku
from app.services import of_import_service as imp


def _prenda_igor(db):
    """Crea la base MODERN + la variante IGOR (material 2000030884) enganchada."""
    base = PrendaCatalogo(codigo="SCH-MF", nombre="CAMISA SCHELLENGER MODERN (BASE)",
                          tipo_base="CAMISA", tipo_cliente="BASE", fit="MODERN",
                          familia="SCHELLENGER MODERN", estado_ficha="PENDIENTE", activo=True)
    db.add(base); db.flush()
    p = PrendaCatalogo(codigo="3LC476", nombre="CAMISA IGOR 3LC476", tipo_base="CAMISA",
                       tipo_cliente="MARCA", base_id=base.id, fit="MODERN", color="AMARILLO",
                       material_sap="2000030884", familia="SCHELLENGER MODERN",
                       estado_ficha="PENDIENTE", activo=True)
    db.add(p); db.flush()
    for i, t in enumerate(["14", "14½", "15", "15½", "16"]):
        db.add(PrendaSku(prenda_catalogo_id=p.id, talla=t, orden=i, activo=True))
    db.commit()
    return p


def _reg(**over):
    base = {
        "numero_of": "4000010011",
        "material_sap": "2000030884",
        "texto_material": "PP-CAM IGOR 3LC476",
        "centro": "PP40",
        "clase_orden": "ZP41",
        "cantidad": 458,
        "autor_sap": "PALVA",
        "fecha_inicio": datetime(2026, 6, 24),
        "fecha_fin": datetime(2026, 9, 24),
        "area_planificacion": "PP40",
        "sociedad": "P040",
        "hora_creacion": time(10, 37, 41),
        "almacen": "PR01",
    }
    base.update(over)
    return base


def test_crear_of_mapea_campos(db):
    r = imp.crear_of_desde_sap(_reg(), db, cliente="John Holden")
    assert r["ok"]
    of = db.query(OrdenFabricacion).filter_by(numero_of="4000010011").one()
    assert of.cliente == "John Holden"
    assert of.material_sap == "2000030884"
    assert of.total_juegos == 458
    assert of.clase_orden == "ZP41"
    assert of.centro == "PP40" and of.sociedad == "P040" and of.almacen == "PR01"
    assert of.autor_sap == "PALVA"
    assert of.estado == EstadoOF.BORRADOR


def test_apt_es_fecha_fin_extrema(db):
    imp.crear_of_desde_sap(_reg(), db)
    of = db.query(OrdenFabricacion).filter_by(numero_of="4000010011").one()
    assert of.fecha_apt == date(2026, 9, 24)          # APT = fin extrema


def test_fecha_sap_combina_fecha_inicio_y_hora(db):
    imp.crear_of_desde_sap(_reg(), db)
    of = db.query(OrdenFabricacion).filter_by(numero_of="4000010011").one()
    assert of.fecha_sap == datetime(2026, 6, 24, 10, 37, 41)


def test_zp41_institucion_con_gates(db):
    imp.crear_of_desde_sap(_reg(clase_orden="ZP41"), db)
    of = db.query(OrdenFabricacion).filter_by(numero_of="4000010011").one()
    assert of.tipo_cliente == TipoClienteEnum.INSTITUCION
    assert of.omitir_gates is False


def test_zp42_marca_con_gates(db):
    imp.crear_of_desde_sap(_reg(clase_orden="ZP42"), db)
    of = db.query(OrdenFabricacion).filter_by(numero_of="4000010011").one()
    assert of.tipo_cliente == TipoClienteEnum.MARCA
    assert of.omitir_gates is False


def test_zp43_sin_gates_y_pendiente(db):
    r = imp.crear_of_desde_sap(_reg(clase_orden="ZP43"), db)
    of = db.query(OrdenFabricacion).filter_by(numero_of="4000010011").one()
    assert of.omitir_gates is True                     # sin gates hasta mapear
    assert "pendiente" in r["mensaje"].lower()


def test_zp44_sin_gates_y_pendiente(db):
    r = imp.crear_of_desde_sap(_reg(clase_orden="ZP44"), db)
    of = db.query(OrdenFabricacion).filter_by(numero_of="4000010011").one()
    assert of.omitir_gates is True
    assert "pendiente" in r["mensaje"].lower()


def test_orden_duplicada_rechazada(db):
    assert imp.crear_of_desde_sap(_reg(), db)["ok"]
    r2 = imp.crear_of_desde_sap(_reg(), db)
    assert not r2["ok"] and "ya existe" in r2["mensaje"].lower()


def test_sin_material_rechazada(db):
    r = imp.crear_of_desde_sap(_reg(material_sap=""), db)
    assert not r["ok"] and "material" in r["mensaje"].lower()


def test_cantidad_invalida_rechazada(db):
    r = imp.crear_of_desde_sap(_reg(cantidad=0), db)
    assert not r["ok"]


def _xlsx(filas):
    """Construye un .xlsx en memoria con encabezados COIS + filas dadas."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Orden", "Número material", "Texto breve material", "Centro",
               "Clase de orden", "Cantidad orden (GMEIN)", "Autor",
               "Fecha inicio extrema", "Fecha fin extrema", "Área pl.nec.",
               "Sociedad", "Hora creación", "Almacén"])
    for f in filas:
        ws.append(f)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_importar_excel_completo(db):
    contenido = _xlsx([
        ["4000010011", "2000030884", "PP-CAM IGOR 3LC476", "PP40", "ZP41", 458,
         "PALVA", datetime(2026, 6, 24), datetime(2026, 9, 24), "PP40", "P040",
         time(10, 37, 41), "PR01"],
        ["4000010012", "2000030886", "PP-CAM MATT 3LC477", "PP40", "ZP42", 300,
         "PALVA", datetime(2026, 6, 25), datetime(2026, 9, 25), "PP40", "P040",
         time(9, 0, 0), "PR01"],
    ])
    res = imp.importar_excel_sap(contenido, db, cliente="John Holden")
    assert res["total"] == 2 and res["creadas"] == 2 and res["errores"] == 0
    assert db.query(OrdenFabricacion).count() == 2
    assert all(o.cliente == "John Holden" for o in db.query(OrdenFabricacion).all())


def test_cliente_se_aplica_a_la_of(db):
    imp.crear_of_desde_sap(_reg(), db, cliente="  Scotiabank  ")
    of = db.query(OrdenFabricacion).filter_by(numero_of="4000010011").one()
    assert of.cliente == "Scotiabank"


def test_sin_cliente_queda_por_definir(db):
    imp.crear_of_desde_sap(_reg(), db)   # sin cliente
    of = db.query(OrdenFabricacion).filter_by(numero_of="4000010011").one()
    assert of.cliente == "POR DEFINIR"


# --- Enlace OF ↔ prenda por material_sap (fase catálogo) ---

def test_of_enlaza_prenda_por_material(db):
    prenda = _prenda_igor(db)
    imp.crear_of_desde_sap(_reg(), db, cliente="John Holden")
    of = db.query(OrdenFabricacion).filter_by(numero_of="4000010011").one()
    assert of.prenda_catalogo_id == prenda.id           # enlazó por material
    assert of.tipo_prenda == "CAMISA"                   # categoría de la prenda enlazada
    assert of.prenda_catalogo.nombre == "CAMISA IGOR 3LC476"  # nombre completo vía relación


def test_of_hereda_fit_y_color_de_la_prenda(db):
    _prenda_igor(db)
    imp.crear_of_desde_sap(_reg(), db, cliente="John Holden")
    of = db.query(OrdenFabricacion).filter_by(numero_of="4000010011").one()
    assert of.prenda_catalogo.fit == "MODERN"           # fit heredado (no de SAP)
    assert of.prenda_catalogo.color == "AMARILLO"


def test_of_sin_prenda_queda_sin_enlace(db):
    # sin crear la prenda: la OF entra pero sin enlace
    r = imp.crear_of_desde_sap(_reg(), db, cliente="John Holden")
    of = db.query(OrdenFabricacion).filter_by(numero_of="4000010011").one()
    assert of.prenda_catalogo_id is None
    assert "no encontrada" in r["mensaje"].lower()


def test_material_sap_es_unico(db):
    from sqlalchemy.exc import IntegrityError
    _prenda_igor(db)
    dup = PrendaCatalogo(codigo="OTRO", nombre="X", tipo_base="CAMISA",
                         tipo_cliente="MARCA", material_sap="2000030884", activo=True)
    db.add(dup)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_variante_engancha_a_su_base(db):
    prenda = _prenda_igor(db)
    assert prenda.base is not None
    assert prenda.base.tipo_cliente == "BASE"
    assert prenda.base.fit == "MODERN"
    # desde la base se ven sus variantes
    assert prenda.id in [v.id for v in prenda.base.variantes]


def test_of_llega_a_la_base_via_variante(db):
    _prenda_igor(db)
    imp.crear_of_desde_sap(_reg(), db, cliente="John Holden")
    of = db.query(OrdenFabricacion).filter_by(numero_of="4000010011").one()
    # la OF enlaza a la variante; la ficha vendrá de variante.base
    assert of.prenda_catalogo.base is not None
    assert of.prenda_catalogo.base.fit == "MODERN"


# --- Herencia de piezas base → variante ---
from app.models.pieza import PlantillaPieza


def _igor_con_piezas_en_base(db):
    igor = _prenda_igor(db)
    base = igor.base
    for i, (nom, fus) in enumerate([("ESPALDA", False), ("CUELLO EXTERIOR", True), ("PUÑO", True)]):
        db.add(PlantillaPieza(prenda_catalogo_id=base.id, codigo=f"SCH-{i}", nombre=nom,
                              material_default="TELA", cantidad_x_prenda=1,
                              fusionado_default=fus, orden=i))
    db.commit()
    return igor


def test_variante_hereda_piezas_de_la_base(db):
    igor = _igor_con_piezas_en_base(db)
    # la variante no tiene piezas propias, pero hereda las 3 de la base
    assert len(igor.plantilla_piezas) == 0
    assert len(igor.piezas_efectivas) == 3
    assert {p.nombre for p in igor.piezas_efectivas} == {"ESPALDA", "CUELLO EXTERIOR", "PUÑO"}


def test_variante_con_ficha_propia_no_hereda(db):
    igor = _igor_con_piezas_en_base(db)
    igor.hereda_ficha = False
    db.commit()
    # con ficha propia (y sin piezas propias) → efectivas = propias = 0
    assert len(igor.piezas_efectivas) == 0


def test_of_genera_piezas_heredadas(db):
    from app.services import of_service
    _igor_con_piezas_en_base(db)
    imp.crear_of_desde_sap(_reg(), db, cliente="John Holden")
    of = db.query(OrdenFabricacion).filter_by(numero_of="4000010011").one()
    of_service.auto_generar_piezas(of, db)
    assert len(of.piezas) == 3                          # generó las piezas heredadas de la base
    assert any(p.fusionado for p in of.piezas)


# --- Herencia de materiales / avíos base → variante ---
from app.models.catalogo import CatalogoMp, CatalogoAvio


def test_variante_hereda_materiales_y_avios(db):
    igor = _prenda_igor(db)
    base = igor.base
    db.add(CatalogoMp(prenda_catalogo_id=base.id, nombre="TELA PRINCIPAL", tipo="TELA_PRINCIPAL",
                      consumo_unitario=1.42, activo=True))
    db.add(CatalogoAvio(prenda_catalogo_id=base.id, seccion="COSTURA", nombre="BOTON 18L",
                        consumo_unitario=12, activo=True))
    db.commit()
    assert len(igor.materiales) == 0 and len(igor.avios) == 0     # no propios
    assert len(igor.materiales_efectivos) == 1                    # heredado de la base
    assert len(igor.avios_efectivos) == 1


def test_ficha_propia_no_hereda_materiales(db):
    igor = _prenda_igor(db)
    base = igor.base
    db.add(CatalogoMp(prenda_catalogo_id=base.id, nombre="TELA", tipo="TELA_PRINCIPAL",
                      consumo_unitario=1.4, activo=True))
    db.commit()
    igor.hereda_ficha = False
    db.commit()
    assert len(igor.materiales_efectivos) == 0                    # ficha propia, sin MP propios


# --- Servicios de terceros + MOD (ficha de costos) ---
from app.models.catalogo import CatalogoServicio, CatalogoMod


def test_variante_hereda_servicios_y_mod(db):
    igor = _prenda_igor(db)
    base = igor.base
    db.add(CatalogoServicio(prenda_catalogo_id=base.id, nombre="BORDADO", costo=0.086, activo=True))
    db.add(CatalogoMod(prenda_catalogo_id=base.id, operacion="COSTURA",
                       min_std=30.42, pct_eficiencia=0.75, costo_minuto=0.08, activo=True))
    db.commit()
    assert len(igor.servicios) == 0 and len(igor.mod_operaciones) == 0   # no propios
    assert len(igor.servicios_efectivos) == 1                            # heredado
    assert len(igor.mod_efectivos) == 1


def test_mod_calcula_min_req_y_subtotal(db):
    igor = _prenda_igor(db)
    op = CatalogoMod(prenda_catalogo_id=igor.base.id, operacion="COSTURA",
                     min_std=30.42, pct_eficiencia=0.75, costo_minuto=0.08, activo=True)
    db.add(op); db.commit()
    assert round(op.min_requerido, 2) == 40.56          # 30.42 / 0.75
    assert round(op.subtotal, 4) == 3.2448              # 40.56 × 0.08


def test_parse_ignora_filas_vacias(db):
    contenido = _xlsx([
        ["4000010011", "2000030884", "PP-CAM IGOR 3LC476", "PP40", "ZP41", 458,
         "PALVA", datetime(2026, 6, 24), datetime(2026, 9, 24), "PP40", "P040",
         time(10, 37, 41), "PR01"],
        [None, None, None, None, None, None, None, None, None, None, None, None, None],
    ])
    filas = imp.parse_excel_sap(contenido)
    assert len(filas) == 1
