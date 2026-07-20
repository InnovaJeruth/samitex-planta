"""
Limpieza controlada: borra TODAS las OFs y TODO el catálogo de prendas
(data de prueba) para reconstruir desde cero.

CONSERVA: usuarios, roles, catálogo de defectos (motivos_rechazo),
plantas externas, parámetros del sistema y fases_catalogo.

Uso:   python limpiar_ofs_catalogo.py
Pide confirmación escribiendo BORRAR antes de tocar nada. Todo en una
sola transacción: si algo falla, no borra nada.
"""
from sqlalchemy import text
from app.database.connection import engine

# Orden FK-safe: primero hijos, al final los padres.
# (ondelete varía por tabla, así que borramos explícito para no depender de cascades.)
TABLAS_EN_ORDEN = [
    # --- nivel hoja (hijos de paquetes / trazos / curvas / catálogo) ---
    "of_reproceso_hitos",
    "of_paquete_rechazos",
    "of_paquete_eventos",
    "of_trazo_movimientos",
    "of_trazo_tallas",
    "curvas_tallas_detalle",
    "curvas_tallas_of",
    "hojas_costos_lineas",
    "prenda_sku_mp_config",
    "prenda_sku_avio_config",
    "prenda_mp_config",
    "prenda_avio_config",
    "ing_ishikawa_causas",
    # --- nivel intermedio (hijos directos de OF / prenda) ---
    "of_paquetes",
    "of_trazos",
    "of_numeracion_reaperturas",
    "avance_registros",
    "of_fase_paradas",
    "of_fase_tiempos",
    "of_fases_estado",
    "of_talla_distribucion",
    "auditoria_documento_of",
    "documentos_of",
    "terc_subproceso_log",
    "terc_recepciones",
    "terc_historial_fechas",
    "ing_sam_registros",
    "ing_paradas_registro",
    "ing_muestreo_obs",
    "ing_tendido_fichas",
    "ing_calidad_inspeccion",
    "ing_ole_diario",
    "ing_fusionado_params",
    "ing_habilitado_cierre",
    "curvas_tallas",
    "hojas_costos",
    # --- nivel medio-alto ---
    "of_piezas",
    "plantilla_piezas",     # piezas plantilla de la prenda base (FK a prendas_catalogo)
    "prenda_skus",
    "catalogo_mp",
    "catalogo_avios",
    "prenda_documentos",
    "precios_historicos",
    # --- padres (al final; ordenes ANTES que prendas por el FK prenda_catalogo_id) ---
    "ordenes_fabricacion",
    "prendas_catalogo",
]

CONSERVADAS = [
    "usuarios", "tokens_revocados", "motivos_rechazo", "plantas_externas",
    "parametros_sistema", "fases_catalogo",
]


def main():
    print("=" * 70)
    print(" LIMPIEZA DE OFs Y CATÁLOGO (data de prueba)")
    print("=" * 70)
    print("\nSe BORRARÁN todas las filas de estas tablas:")
    for t in TABLAS_EN_ORDEN:
        print("   -", t)
    print("\nSe CONSERVAN:", ", ".join(CONSERVADAS))
    print()
    resp = input('Escribe BORRAR para confirmar (cualquier otra cosa cancela): ').strip()
    if resp != "BORRAR":
        print("Cancelado. No se tocó nada.")
        return

    with engine.begin() as conn:  # transacción única: rollback automático si falla
        insp_tablas = set(conn.exec_driver_sql(
            "SELECT name FROM sys.tables").scalars().all()) if engine.dialect.name == "mssql" else None
        total = 0
        for t in TABLAS_EN_ORDEN:
            # salta tablas que no existan (defensivo entre entornos)
            if insp_tablas is not None and t not in insp_tablas:
                print(f"   (omitida, no existe) {t}")
                continue
            try:
                n_antes = conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
                conn.execute(text(f"DELETE FROM {t}"))
                total += (n_antes or 0)
                print(f"   borradas {n_antes:>6} de {t}")
            except Exception as e:
                print(f"   ERROR en {t}: {e}")
                raise  # aborta toda la transacción
    print(f"\nListo. {total} filas borradas. Catálogo y OFs vacíos, config conservada.")


if __name__ == "__main__":
    main()
