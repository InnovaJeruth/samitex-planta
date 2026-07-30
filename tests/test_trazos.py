"""
Tests del servicio de trazos/placas (Fase A alineada al Excel).
SQLite en memoria (fixture `db` de conftest.py).
"""
import pytest
from datetime import date
from fastapi import HTTPException

from app.models.of import OrdenFabricacion, EstadoOF, TipoClienteEnum, EstadoDocsEnum, OFTallaDistribucion
from app.models.catalogo import PrendaCatalogo, PrendaSku, CatalogoMp
from app.services import trazo_service
from app.constants import MAX_CAPAS_DEFAULT


def _setup(db):
    """OF con curva S=10, M=20, L=15 (45) y consumo de tela 1.2 m/prenda en la HDC."""
    prenda = PrendaCatalogo(codigo="CAM-TZ", nombre="Camisa TZ", tipo_base="CAMISA", tipo_cliente="MARCA")
    db.add(prenda); db.flush()
    db.add(CatalogoMp(prenda_catalogo_id=prenda.id, nombre="TELA X", tipo="TELA_PRINCIPAL", consumo_unitario=1.2))
    skus = {}
    for talla in ["S", "M", "L"]:
        sku = PrendaSku(prenda_catalogo_id=prenda.id, talla=talla, activo=True)
        db.add(sku); db.flush(); skus[talla] = sku.id
    of = OrdenFabricacion(
        numero_of="OF-TZ", cliente="C", tipo_prenda="CAMISA", total_juegos=45,
        fecha_creacion=date.today(), estado=EstadoOF.ACTIVA,
        tipo_cliente=TipoClienteEnum.MARCA, estado_docs=EstadoDocsEnum.COMPLETA,
        prenda_catalogo_id=prenda.id,
    )
    db.add(of); db.flush()
    for talla, cant in [("S", 10), ("M", 20), ("L", 15)]:
        db.add(OFTallaDistribucion(of_id=of.id, sku_id=skus[talla], cantidad=cant))
    db.commit()
    return of, skus


class TestDerivacion:
    def test_cantidad_es_capas_por_veces(self, db):
        of, skus = _setup(db)
        tz = trazo_service.crear_trazo(of.id, "P1", 2.5, 10,
            [{"sku_id": skus["S"], "veces": 1}, {"sku_id": skus["M"], "veces": 2}], db)
        por = {t.talla: t.cantidad for t in tz.tallas}
        assert por["S"] == 10      # 10 capas × 1
        assert por["M"] == 20      # 10 capas × 2
        assert tz.total_prendas == 30

    def test_metraje_es_capas_por_largo(self, db):
        of, skus = _setup(db)
        tz = trazo_service.crear_trazo(of.id, "P1", 2.5, 10,
            [{"sku_id": skus["S"], "veces": 1}], db)
        assert tz.metraje == 25.0  # 10 × 2.5


class TestTope:
    def test_default_80(self, db):
        of, _ = _setup(db)
        assert trazo_service.max_capas_of(of) == MAX_CAPAS_DEFAULT == 80

    def test_editable_por_of(self, db):
        of, _ = _setup(db)
        trazo_service.set_max_capas(of.id, 40, db)
        db.refresh(of)
        assert trazo_service.max_capas_of(of) == 40

    def test_rechaza_capas_sobre_tope(self, db):
        of, skus = _setup(db)
        trazo_service.set_max_capas(of.id, 10, db)
        with pytest.raises(HTTPException) as exc:
            trazo_service.crear_trazo(of.id, "P1", 2.0, 11, [{"sku_id": skus["S"], "veces": 1}], db)
        assert exc.value.status_code == 400


class TestCobertura:
    def test_completa_con_veces(self, db):
        of, skus = _setup(db)
        trazo_service.crear_trazo(of.id, "P1", 2.0, 10,
            [{"sku_id": skus["S"], "veces": 1}, {"sku_id": skus["M"], "veces": 1}], db)  # S10 M10
        trazo_service.crear_trazo(of.id, "P2", 2.0, 10, [{"sku_id": skus["M"], "veces": 1}], db)  # M10
        trazo_service.crear_trazo(of.id, "P3", 2.0, 15, [{"sku_id": skus["L"], "veces": 1}], db)  # L15
        v = trazo_service.validar_cobertura(of.id, db)
        assert v["cubierto"] is True
        assert v["total_asignado"] == 45
        assert all(t["restante"] == 0 for t in v["por_talla"])

    def test_talla_fuera_de_curva(self, db):
        of, skus = _setup(db)
        with pytest.raises(HTTPException) as exc:
            trazo_service.crear_trazo(of.id, "PX", None, 5, [{"sku_id": 99999, "veces": 1}], db)
        assert exc.value.status_code == 400

    def test_rechaza_exceder_pedido(self, db):
        of, skus = _setup(db)
        # meta S=10; 5 capas × 3 veces = 15 > 10 → debe rechazar
        with pytest.raises(HTTPException) as exc:
            trazo_service.crear_trazo(of.id, "P1", 2.0, 5, [{"sku_id": skus["S"], "veces": 3}], db)
        assert exc.value.status_code == 400
        assert "supera" in exc.value.detail.lower()

    def test_acumulado_no_excede_entre_placas(self, db):
        of, skus = _setup(db)
        # S=10: primera placa 8, segunda 5 (8+5=13>10) → rechaza
        trazo_service.crear_trazo(of.id, "P1", 2.0, 8, [{"sku_id": skus["S"], "veces": 1}], db)
        with pytest.raises(HTTPException) as exc:
            trazo_service.crear_trazo(of.id, "P2", 2.0, 5, [{"sku_id": skus["S"], "veces": 1}], db)
        assert exc.value.status_code == 400


class TestFinAutomatico:
    def test_fin_tizado_al_cubrir_pedido(self, db):
        from app.models.fase import OFFaseTiempos
        of, skus = _setup(db)
        trazo_service.crear_trazo(of.id, "P1", 2.0, 10,
            [{"sku_id": skus["S"], "veces": 1}, {"sku_id": skus["M"], "veces": 1}], db)
        trazo_service.crear_trazo(of.id, "P2", 2.0, 10, [{"sku_id": skus["M"], "veces": 1}], db)
        # aún falta L → pedido no cubierto → sin fin de F1
        ft = db.query(OFFaseTiempos).filter_by(of_id=of.id, fase_id="F1").first()
        assert ft is None or ft.fin_real is None
        # se cubre el pedido → fin de F1 (tizado) automático
        trazo_service.crear_trazo(of.id, "P3", 2.0, 15, [{"sku_id": skus["L"], "veces": 1}], db)
        ft = db.query(OFFaseTiempos).filter_by(of_id=of.id, fase_id="F1").first()
        assert ft is not None and ft.fin_real is not None


class TestFasesTela:
    def test_iniciar_marca_inicio(self, db):
        of, skus = _setup(db)
        trazo_service.iniciar_fase_tela(of.id, "tizado", db)
        info = {f["fase"]: f for f in trazo_service.fases_tela_info(of.id, db)}
        assert info["tizado"]["inicio"] is not None
        assert info["tizado"]["estado"] == "en_curso"

    def test_no_iniciar_tendido_antes_de_tizado(self, db):
        of, skus = _setup(db)
        with pytest.raises(HTTPException) as exc:
            trazo_service.iniciar_fase_tela(of.id, "tendido", db)
        assert exc.value.status_code == 400


class TestSyncPieza:
    def test_placas_completan_marca_pieza_f1(self, db):
        from app.models.pieza import OFPieza
        from app.models.fase import OFFaseEstado
        of, skus = _setup(db)
        p1 = OFPieza(of_id=of.id, nombre="Delantero", material="TELA", cantidad_x_prenda=1)
        p2 = OFPieza(of_id=of.id, nombre="Espalda", material="TELA", cantidad_x_prenda=1)
        db.add_all([p1, p2]); db.flush()
        for p in (p1, p2):
            db.add(OFFaseEstado(of_id=of.id, pieza_id=p.id, fase_id="F1",
                                cantidad_actual=0, max_cantidad=45, completada=False))
        db.commit()
        trazo_service.crear_trazo(of.id, "P1", 2.0, 10, [{"sku_id": skus["S"], "veces": 1}, {"sku_id": skus["M"], "veces": 1}], db)
        trazo_service.crear_trazo(of.id, "P2", 2.0, 10, [{"sku_id": skus["M"], "veces": 1}], db)
        trazo_service.crear_trazo(of.id, "P3", 2.0, 15, [{"sku_id": skus["L"], "veces": 1}], db)
        estados = db.query(OFFaseEstado).filter_by(of_id=of.id, fase_id="F1").all()
        assert estados and all(e.completada for e in estados)


class TestConsumo:
    def test_proyectado_y_real(self, db):
        of, skus = _setup(db)
        # 10 capas × largo 1.2 con 1 talla ×1 → 10 prendas, 12 m → real 1.2
        trazo_service.crear_trazo(of.id, "P1", 1.2, 10, [{"sku_id": skus["S"], "veces": 1}], db)
        r = trazo_service.resumen_consumo(of.id, db)
        assert r["proyectado"] == 1.2
        assert r["prendas"] == 10
        assert r["metros"] == 12.0
        assert r["real"] == 1.2
        assert r["desvio"] == 0.0
