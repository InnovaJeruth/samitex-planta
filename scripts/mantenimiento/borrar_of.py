"""
Borra UNA OF por su número (y todos sus registros hijos), sin tocar el catálogo.
Útil para reimportar/probar.

Uso:  python borrar_of.py 4000010011
      python borrar_of.py            (pregunta el número)
"""
import sys
from sqlalchemy import text
from app.database.connection import engine

# DELETEs scoped al of_id, en orden FK-safe (hijos → OF).
_SQL = [
    # hijos de paquetes
    ("of_reproceso_hitos",
     "DELETE FROM of_reproceso_hitos WHERE rechazo_id IN "
     "(SELECT id FROM of_paquete_rechazos WHERE paquete_id IN "
     "(SELECT id FROM of_paquetes WHERE of_id=:id))"),
    ("of_paquete_rechazos",
     "DELETE FROM of_paquete_rechazos WHERE paquete_id IN "
     "(SELECT id FROM of_paquetes WHERE of_id=:id)"),
    ("of_paquete_eventos",
     "DELETE FROM of_paquete_eventos WHERE paquete_id IN "
     "(SELECT id FROM of_paquetes WHERE of_id=:id)"),
    ("of_paquetes", "DELETE FROM of_paquetes WHERE of_id=:id"),
    # hijos de trazos
    ("of_trazo_movimientos",
     "DELETE FROM of_trazo_movimientos WHERE trazo_id IN "
     "(SELECT id FROM of_trazos WHERE of_id=:id)"),
    ("of_trazo_tallas",
     "DELETE FROM of_trazo_tallas WHERE trazo_id IN "
     "(SELECT id FROM of_trazos WHERE of_id=:id)"),
    ("of_trazos", "DELETE FROM of_trazos WHERE of_id=:id"),
    # hijos directos de la OF
    ("of_numeracion_reaperturas", "DELETE FROM of_numeracion_reaperturas WHERE of_id=:id"),
    ("avance_registros",          "DELETE FROM avance_registros WHERE of_id=:id"),
    ("of_fase_paradas",           "DELETE FROM of_fase_paradas WHERE of_id=:id"),
    ("of_fase_tiempos",           "DELETE FROM of_fase_tiempos WHERE of_id=:id"),
    ("of_fases_estado",           "DELETE FROM of_fases_estado WHERE of_id=:id"),
    ("of_talla_distribucion",     "DELETE FROM of_talla_distribucion WHERE of_id=:id"),
    ("curvas_tallas_of",          "DELETE FROM curvas_tallas_of WHERE of_id=:id"),
    ("auditoria_documento_of",    "DELETE FROM auditoria_documento_of WHERE of_id=:id"),
    ("documentos_of",             "DELETE FROM documentos_of WHERE of_id=:id"),
    ("terc_subproceso_log",       "DELETE FROM terc_subproceso_log WHERE of_id=:id"),
    ("terc_recepciones",          "DELETE FROM terc_recepciones WHERE of_id=:id"),
    ("terc_historial_fechas",     "DELETE FROM terc_historial_fechas WHERE of_id=:id"),
    ("ing_sam_registros",         "DELETE FROM ing_sam_registros WHERE of_id=:id"),
    ("ing_paradas_registro",      "DELETE FROM ing_paradas_registro WHERE of_id=:id"),
    ("ing_muestreo_obs",          "DELETE FROM ing_muestreo_obs WHERE of_id=:id"),
    ("ing_tendido_fichas",        "DELETE FROM ing_tendido_fichas WHERE of_id=:id"),
    ("ing_calidad_inspeccion",    "DELETE FROM ing_calidad_inspeccion WHERE of_id=:id"),
    ("ing_ole_diario",            "DELETE FROM ing_ole_diario WHERE of_id=:id"),
    ("ing_fusionado_params",      "DELETE FROM ing_fusionado_params WHERE of_id=:id"),
    ("ing_habilitado_cierre",     "DELETE FROM ing_habilitado_cierre WHERE of_id=:id"),
    ("of_piezas",                 "DELETE FROM of_piezas WHERE of_id=:id"),
    ("ordenes_fabricacion",       "DELETE FROM ordenes_fabricacion WHERE id=:id"),
]


def main():
    numero = sys.argv[1] if len(sys.argv) > 1 else input("N° de OF a borrar: ").strip()
    if not numero:
        print("Sin número. Cancelado.")
        return
    with engine.begin() as conn:
        of_id = conn.execute(
            text("SELECT id FROM ordenes_fabricacion WHERE numero_of=:n"),
            {"n": numero}).scalar()
        if not of_id:
            print(f"No existe una OF con número {numero}.")
            return
        total = 0
        for _, sql in _SQL:
            n = conn.execute(text(sql), {"id": of_id}).rowcount
            total += (n or 0)
        print(f"OF {numero} (id={of_id}) borrada. {total} filas eliminadas (OF + hijos).")


if __name__ == "__main__":
    main()
