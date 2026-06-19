from datetime import date
from enum import Enum


class EstadoSemaforo(str, Enum):
    VENCIDO   = "VENCIDO"    # FechaAPT < hoy, no finalizada
    ALERTA    = "ALERTA"     # ≤15 días restantes, no finalizada
    A_TIEMPO  = "A_TIEMPO"   # >15 días restantes, no finalizada
    OK_FECHA  = "OK_FECHA"   # finalizada antes/en fecha APT
    OK_TARDE  = "OK_TARDE"   # finalizada después de fecha APT
    SIN_FECHA = "SIN_FECHA"  # sin fecha APT


COLORES = {
    EstadoSemaforo.VENCIDO:   "#c00000",
    EstadoSemaforo.ALERTA:    "#bf9000",
    EstadoSemaforo.A_TIEMPO:  "#0070c0",
    EstadoSemaforo.OK_FECHA:  "#2e7d32",
    EstadoSemaforo.OK_TARDE:  "#6b6b00",
    EstadoSemaforo.SIN_FECHA: "#777777",
}


def calcular_semaforo(
    fecha_apt: date | None,
    completada: bool,
    fecha_completado: date | None = None,
) -> dict:
    hoy = date.today()

    if completada:
        if fecha_apt and fecha_completado:
            estado = EstadoSemaforo.OK_FECHA if fecha_completado <= fecha_apt else EstadoSemaforo.OK_TARDE
        else:
            estado = EstadoSemaforo.OK_FECHA
    elif not fecha_apt:
        estado = EstadoSemaforo.SIN_FECHA
    else:
        dias = (fecha_apt - hoy).days
        if dias < 0:
            estado = EstadoSemaforo.VENCIDO
        elif dias <= 15:
            estado = EstadoSemaforo.ALERTA
        else:
            estado = EstadoSemaforo.A_TIEMPO

    return {
        "estado": estado.value,
        "color": COLORES[estado],
        "dias_restantes": (fecha_apt - hoy).days if fecha_apt and not completada else None,
    }
