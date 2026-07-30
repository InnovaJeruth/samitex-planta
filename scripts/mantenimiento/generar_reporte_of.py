"""
Genera un archivo .md con el estado actual de todas las OFs
para análisis en Obsidian u otras herramientas.

Uso:
    python generar_reporte_of.py              → reporte_ofs.md (todas las OFs)
    python generar_reporte_of.py 48965        → reporte_of_48965.md (una OF)
    python generar_reporte_of.py --activas    → solo EN_PROCESO y ACTIVAS
"""
import sys
from datetime import date, datetime
from pathlib import Path

# Reutiliza la configuración y modelos del proyecto
from app.database.connection import SessionLocal
import app.models.usuario  # registra Usuario en el mapper de SQLAlchemy
import app.models.planta   # registra PlantaExterna en el mapper de SQLAlchemy
from app.models.of import OrdenFabricacion, EstadoOF
from app.models.pieza import OFPieza
from app.models.fase import OFFaseEstado, OFFaseTiempos, AvanceRegistro, OFFaseParada
from app.constants import ORDEN_FASES, NOMBRES_FASE

ICONOS_ESTADO = {
    "BORRADOR":   "⬜",
    "ACTIVA":     "🔵",
    "EN_PROCESO": "🟡",
    "COMPLETADA": "✅",
    "ANULADA":    "🔴",
}

ICONOS_FASE = {
    "f1_tizado":    "✏️",
    "f2_tendido":   "📐",
    "f3_corte":     "✂️",
    "f4_numerado":  "🔢",
    "f5_fusionado": "🔥",
    "f6_calidad":   "🔍",
    "f7_habilitado":"📦",
}

def fmt(v):
    if v is None:
        return "—"
    if isinstance(v, (date, datetime)):
        return v.strftime("%d/%m/%Y")
    if hasattr(v, "value"):
        return v.value
    return str(v)

def pct_barra(pct: float, ancho=20) -> str:
    lleno = int(pct / 100 * ancho)
    return "█" * lleno + "░" * (ancho - lleno) + f" {pct:.0f}%"

def calcular_avance_of(piezas_data):
    """Retorna % promedio de avance de la OF basado en F7."""
    if not piezas_data:
        return 0.0
    completadas = sum(1 for p in piezas_data if p["f7_completa"])
    return round(completadas / len(piezas_data) * 100, 1)

def get_fases_pieza(db, pieza_id):
    fases = db.query(OFFaseEstado).filter(OFFaseEstado.pieza_id == pieza_id).all()
    return {f.fase_id: f for f in fases}

def reporte_of(of, db) -> str:
    estado_val = of.estado.value if hasattr(of.estado, "value") else str(of.estado)
    icono = ICONOS_ESTADO.get(estado_val, "•")
    lines = []

    # Cabecera
    lines.append(f"## {icono} OF {of.numero_of} — {of.cliente}")
    lines.append("")
    lines.append(f"> **Prenda:** {fmt(of.tipo_prenda)} · **Juegos:** {of.total_juegos} · **Estado:** {estado_val}")
    lines.append(f"> **APT:** {fmt(of.fecha_apt)} · **Inicio plan:** {fmt(of.fecha_inicio_plan)} · **Tipo cliente:** {fmt(of.tipo_cliente)}")
    if of.tercerizado:
        lines.append(f"> ⚠️ **Tercerizada** → {(of.planta.nombre if of.planta else None) or '—'} | Estado: {of.estado_tercerizado or '—'} | Recepción est.: {fmt(of.fecha_recepcion_est)}")
    lines.append("")

    # Piezas y fases
    piezas = db.query(OFPieza).filter(OFPieza.of_id == of.id).all()
    if not piezas:
        lines.append("_Sin piezas registradas._")
        lines.append("")
        return "\n".join(lines)

    piezas_data = []
    tabla_fases = []

    # Encabezado tabla
    fase_cols = " | ".join(NOMBRES_FASE.get(f, f) for f in ORDEN_FASES)
    tabla_fases.append(f"| Pieza | {fase_cols} |")
    tabla_fases.append("|" + "---|" * (len(ORDEN_FASES) + 1))

    for p in piezas:
        fases = get_fases_pieza(db, p.id)
        fila = [p.nombre]
        f7_completa = False
        for fase_id in ORDEN_FASES:
            f = fases.get(fase_id)
            if not f:
                fila.append("—")
            elif f.completada:
                fila.append("✅")
                if fase_id == "f7_habilitado":
                    f7_completa = True
            elif f.cantidad_actual and f.cantidad_actual > 0:
                pct = round(f.cantidad_actual / f.max_cantidad * 100) if f.max_cantidad else 0
                fila.append(f"🔄{pct}%")
            else:
                fila.append("⏳")
        tabla_fases.append("| " + " | ".join(fila) + " |")
        piezas_data.append({"nombre": p.nombre, "f7_completa": f7_completa})

    avance_total = calcular_avance_of(piezas_data)
    lines.append(f"**Avance global:** {pct_barra(avance_total)}")
    lines.append("")
    lines.append("### Avance por pieza y fase")
    lines.append("")
    lines.extend(tabla_fases)
    lines.append("")

    # Tiempos programados vs reales
    tiempos = db.query(OFFaseTiempos).filter(OFFaseTiempos.of_id == of.id).all()
    if tiempos:
        lines.append("### Programado vs Real")
        lines.append("")
        lines.append("| Fase | Inicio prog. | Fin prog. | Inicio real | Fin real |")
        lines.append("|---|---|---|---|---|")
        for t in tiempos:
            nombre_fase = NOMBRES_FASE.get(t.fase_id, t.fase_id)
            lines.append(f"| {nombre_fase} | {fmt(t.inicio_programado)} | {fmt(t.fin_programado)} | {fmt(t.inicio_real)} | {fmt(t.fin_real)} |")
        lines.append("")

    # Últimos avances
    avances = (
        db.query(AvanceRegistro)
        .filter(AvanceRegistro.of_id == of.id, AvanceRegistro.revertido == False)
        .order_by(AvanceRegistro.created_at.desc())
        .limit(5)
        .all()
    )
    if avances:
        lines.append("### Últimos registros")
        lines.append("")
        lines.append("| Fecha | Fase | Cantidad | Observación |")
        lines.append("|---|---|---|---|")
        for a in avances:
            obs = (a.observacion or "—")[:60]
            lines.append(f"| {fmt(a.created_at)} | {NOMBRES_FASE.get(a.fase_id, a.fase_id)} | {a.cantidad} | {obs} |")
        lines.append("")

    # Paradas activas
    paradas = (
        db.query(OFFaseParada)
        .filter(OFFaseParada.of_id == of.id, OFFaseParada.fin_parada.is_(None))
        .all()
    )
    if paradas:
        lines.append("### ⚠️ Paradas activas")
        lines.append("")
        for par in paradas:
            lines.append(f"- **{NOMBRES_FASE.get(par.fase_id, par.fase_id)}** — Motivo: {par.motivo or '—'} (desde {fmt(par.inicio_parada)})")
        lines.append("")

    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def generar_md(filtro_numero: str = None, solo_activas: bool = False) -> str:
    db = SessionLocal()
    try:
        query = db.query(OrdenFabricacion)

        if filtro_numero:
            query = query.filter(OrdenFabricacion.numero_of == filtro_numero)
        elif solo_activas:
            query = query.filter(OrdenFabricacion.estado.in_([EstadoOF.ACTIVA, EstadoOF.EN_PROCESO]))
        else:
            query = query.filter(OrdenFabricacion.estado != EstadoOF.ANULADA)

        ofs = query.order_by(OrdenFabricacion.fecha_apt).all()

        if not ofs:
            return "# Sin OFs encontradas\n"

        ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
        lines = [
            f"# Reporte OFs — Samitex Planta",
            f"",
            f"> Generado: {ahora} · Total OFs: {len(ofs)}",
            f"",
            f"**Leyenda:** ✅ Completa · 🔄 En curso · ⏳ Pendiente · — Sin datos",
            f"",
            f"---",
            f"",
        ]

        # Resumen rápido
        lines.append("## Resumen")
        lines.append("")
        lines.append("| OF | Cliente | Prenda | Juegos | Estado | APT | Inicio plan |")
        lines.append("|---|---|---|---|---|---|---|")
        for of in ofs:
            estado_val = of.estado.value if hasattr(of.estado, "value") else str(of.estado)
            icono = ICONOS_ESTADO.get(estado_val, "•")
            lines.append(
                f"| {of.numero_of} | {of.cliente} | {fmt(of.tipo_prenda)} | "
                f"{of.total_juegos} | {icono} {estado_val} | {fmt(of.fecha_apt)} | {fmt(of.fecha_inicio_plan)} |"
            )
        lines.append("")
        lines.append("---")
        lines.append("")

        # Detalle por OF
        lines.append("## Detalle por OF")
        lines.append("")
        for of in ofs:
            lines.append(reporte_of(of, db))

        lines.append(f"*Generado automáticamente por generar_reporte_of.py · {ahora}*")
        return "\n".join(lines)

    finally:
        db.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    solo_activas = "--activas" in args
    numero_of = next((a for a in args if a.isdigit()), None)

    contenido = generar_md(filtro_numero=numero_of, solo_activas=solo_activas)

    if numero_of:
        nombre_archivo = f"reporte_of_{numero_of}.md"
    elif solo_activas:
        nombre_archivo = "reporte_ofs_activas.md"
    else:
        nombre_archivo = "reporte_ofs.md"

    Path(nombre_archivo).write_text(contenido, encoding="utf-8")
    print(f"✓ Generado: {nombre_archivo} ({len(contenido)} caracteres)")
