"""
Paquetes de numeración (Hoja de numeración — sale del Numerado F4).

Un paquete = una talla + un color (vía sku_id), con su rango de numeración
correlativo y su flujo Numerado → Habilitado → Calidad → Entregado.

Normalizado: no se guarda color/talla (salen del SKU), ni numero_hasta ni el
corte real (derivados). `estado` es caché del último evento (mismo patrón que
of_fases_estado / of_trazos).
"""
from sqlalchemy import Boolean, Column, Integer, String, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.connection import Base

# Estados del flujo de un paquete.
# El paquete nace HABILITADO (numerado + agrupado + sticker), pasa a POR_VALIDAR
# (listo para Calidad, tras fusionado si aplica), y termina ENTREGADO (a costura).
# STAND_BY = validado con piezas rechazadas esperando reproceso.
ESTADO_HABILITADO   = "HABILITADO"
ESTADO_FUSIONADO    = "FUSIONADO"     # en fusionado (solo prendas con piezas que fusionan)
ESTADO_POR_VALIDAR  = "POR_VALIDAR"
ESTADO_STANDBY      = "STAND_BY"
ESTADO_ENTREGADO    = "ENTREGADO"

# Orden del flujo (referencia)
ORDEN_ESTADOS = [ESTADO_HABILITADO, ESTADO_FUSIONADO, ESTADO_POR_VALIDAR,
                 ESTADO_STANDBY, ESTADO_ENTREGADO]

# --- Calidad / Reprocesos (Q1, aditivo) -------------------------------------
# Tipo de destino que Calidad asigna a cada rechazo
TIPO_REPROCESO = "REPROCESO"   # se arregla (recorte / refusión)
TIPO_REHACER   = "REHACER"     # se corta de nuevo (consume tela)
TIPO_MERMA     = "MERMA"       # no recuperable (segunda)
TIPOS_RECHAZO  = (TIPO_REPROCESO, TIPO_REHACER, TIPO_MERMA)

# Ciclo de vida de un rechazo (pieza)
RECHAZO_PENDIENTE    = "PENDIENTE"
RECHAZO_EN_REPROCESO = "EN_REPROCESO"
RECHAZO_ESPERA_TELA  = "ESPERA_TELA"   # rehacer sin tela: espera SOLPED/rollo (PCP/Almacén en SAP)
RECHAZO_REINGRESADO  = "REINGRESADO"
RECHAZO_MERMA        = "MERMA"

# Etapas de la ruta de rehacer (re-fabricación de la pieza, con trazabilidad)
ETAPA_TIZADO    = "TIZADO"
ETAPA_TENDIDO   = "TENDIDO"
ETAPA_CORTE     = "CORTE"
ETAPA_NUMERADO  = "NUMERADO"
ETAPA_FUSIONADO = "FUSIONADO"
ETAPAS_REHACER_BASE = [ETAPA_TIZADO, ETAPA_TENDIDO, ETAPA_CORTE, ETAPA_NUMERADO]

# Severidad del defecto (informativo por ahora)
SEV_MAYOR = "MAYOR"
SEV_MENOR = "MENOR"

# Destinos de un rechazo (a dónde va la pieza según el defecto).
# Áreas internas de corte (tienen bandeja de reproceso):
DEST_CORTE       = "CORTE"
DEST_FUSIONADO   = "FUSIONADO"
DEST_DESMANCHADO = "DESMANCHADO"
DEST_HABILITADO  = "HABILITADO"
DEST_TENDIDO     = "TENDIDO"
DEST_TIZADO      = "TIZADO"
# Estaciones de corte que reprocesan y re-fabrican (bandeja de Reprocesos):
DESTINOS_CON_BANDEJA = (DEST_CORTE, DEST_FUSIONADO,
                        DEST_HABILITADO, DEST_TENDIDO, DEST_TIZADO)
# Fuera de corte (derivado / fin):
DEST_MODELISTA = "MODELISTA"   # error de molde (Ingeniería)
DEST_GERENCIA  = "GERENCIA"    # el gerente de planta decide: aprobar o rehacer
DEST_EXTERNO   = "EXTERNO"     # falta bordado / sublimado / avíos
DEST_MERMA     = "MERMA"       # irrecuperable (lo retira corte)
# Destinos que "arreglan y devuelven" con un OK → reingresa a Calidad (módulo Dar OK):
DESTINOS_OK = (DEST_MODELISTA, DEST_EXTERNO, DEST_DESMANCHADO)


class OFPaquete(Base):
    __tablename__ = "of_paquetes"

    id           = Column(Integer, primary_key=True, index=True)
    of_id        = Column(Integer, ForeignKey("ordenes_fabricacion.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    sku_id       = Column(Integer, ForeignKey("prenda_skus.id", ondelete="NO ACTION"), nullable=False)
    pieza_id     = Column(Integer, ForeignKey("of_piezas.id", ondelete="CASCADE"), nullable=False, index=True)
    numero       = Column(Integer, nullable=False)          # nº de bulto dentro de la pieza (sticker)
    numero_desde = Column(Integer, nullable=False)          # nº de prenda inicial del rango
    cantidad     = Column(Integer, nullable=False)          # prendas del bulto
    estado       = Column(String(15), nullable=False, default=ESTADO_HABILITADO)
    fusionado_inicio = Column(DateTime, nullable=True)   # cuándo empezó el fusionado
    fusionado_fin    = Column(DateTime, nullable=True)   # cuándo terminó
    created_at   = Column(DateTime, server_default=func.now())
    updated_at   = Column(DateTime, server_default=func.now(), onupdate=func.now())

    of      = relationship("OrdenFabricacion")
    sku     = relationship("PrendaSku")
    pieza   = relationship("OFPieza")
    eventos = relationship("OFPaqueteEvento", back_populates="paquete",
                           cascade="all, delete-orphan", order_by="OFPaqueteEvento.created_at")
    rechazos = relationship("OFPaqueteRechazo", back_populates="paquete",
                            cascade="all, delete-orphan", order_by="OFPaqueteRechazo.created_at")

    __table_args__ = (
        UniqueConstraint("of_id", "pieza_id", "numero", name="uq_of_paquete_pieza_num"),
        Index("ix_of_paquetes_of_sku", "of_id", "sku_id"),
    )

    @property
    def numero_hasta(self):
        return self.numero_desde + (self.cantidad or 0) - 1

    @property
    def talla(self):
        return self.sku.talla if self.sku else None

    @property
    def color(self):
        return self.sku.prenda.color if (self.sku and self.sku.prenda) else None

    @property
    def pieza_nombre(self):
        return self.pieza.nombre if self.pieza else None

    @property
    def fusiona(self):
        return bool(self.pieza and self.pieza.fusionado)

    @property
    def fusionado_en_proceso(self):
        return bool(self.fusionado_inicio and not self.fusionado_fin)


class OFPaqueteEvento(Base):
    """Historial/auditoría del flujo de un paquete (quién y cuándo)."""
    __tablename__ = "of_paquete_eventos"

    id         = Column(Integer, primary_key=True, index=True)
    paquete_id = Column(Integer, ForeignKey("of_paquetes.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    estado     = Column(String(15), nullable=False)
    motivo     = Column(String(200), nullable=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    paquete = relationship("OFPaquete", back_populates="eventos")
    usuario = relationship("Usuario")


class MotivoRechazo(Base):
    """Catálogo de defectos de corte (CR01…CR53), de los formatos FR-GC-CR-001/002/003.

    Normalizado: el tipo de reproceso y la fase destino NO viven aquí (los decide
    Calidad en cada rechazo), solo el defecto en sí.
    """
    __tablename__ = "motivos_rechazo"

    id          = Column(Integer, primary_key=True, index=True)
    codigo      = Column(String(10), nullable=False, unique=True)   # CR01…CR53
    descripcion = Column(String(120), nullable=False)
    severidad   = Column(String(10), nullable=True)                 # MAYOR / MENOR (informativo)
    destino     = Column(String(20), nullable=True)                 # área destino del defecto (fija)
    destinos_alt = Column(String(80), nullable=True)                # alternativas separadas por coma (Calidad elige)
    rehacer_default = Column(Boolean, nullable=False, default=False) # irrecuperable → siempre rehacer (ej. hueco)
    activo      = Column(Boolean, nullable=False, default=True)


class OFPaqueteRechazo(Base):
    """Unidades rechazadas de un paquete, con su defecto y el destino que asigna Calidad.

    `tipo` y `fase_destino` los decide Calidad por cada rechazo (no salen del
    catálogo). `estado` es el ciclo de vida propio del rechazo.
    """
    __tablename__ = "of_paquete_rechazos"

    id           = Column(Integer, primary_key=True, index=True)
    paquete_id   = Column(Integer, ForeignKey("of_paquetes.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    motivo_id    = Column(Integer, ForeignKey("motivos_rechazo.id"), nullable=False)
    cantidad     = Column(Integer, nullable=False)
    tipo         = Column(String(15), nullable=True)    # (legado) REPROCESO / REHACER / MERMA
    fase_destino = Column(String(10), nullable=True)    # (legado)
    destino      = Column(String(20), nullable=True)    # área destino (CORTE, FUSIONADO, MODELISTA, GERENCIA, MERMA…)
    rehacer      = Column(Boolean, nullable=False, default=False)   # corta nueva (usa tela)
    solped       = Column(String(40), nullable=True)    # N° SOLPED (SAP) para la tela del rehacer — trazabilidad
    etapa        = Column(String(15), nullable=True)    # etapa actual de la ruta de rehacer (TIZADO…FUSIONADO)
    estado       = Column(String(15), nullable=False, default=RECHAZO_PENDIENTE)
    usuario_id   = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    created_at   = Column(DateTime, server_default=func.now())
    updated_at   = Column(DateTime, server_default=func.now(), onupdate=func.now())

    paquete = relationship("OFPaquete", back_populates="rechazos")
    motivo  = relationship("MotivoRechazo")
    usuario = relationship("Usuario")
    hitos   = relationship("OFReprocesoHito", back_populates="rechazo",
                           cascade="all, delete-orphan", order_by="OFReprocesoHito.at")


class OFReprocesoHito(Base):
    """Traza de la ruta de rehacer: cada etapa con su hora y quién la marcó."""
    __tablename__ = "of_reproceso_hitos"

    id         = Column(Integer, primary_key=True, index=True)
    rechazo_id = Column(Integer, ForeignKey("of_paquete_rechazos.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    etapa      = Column(String(15), nullable=False)
    at         = Column(DateTime, server_default=func.now())
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)

    rechazo = relationship("OFPaqueteRechazo", back_populates="hitos")
    usuario = relationship("Usuario")


class OFNumeracionReapertura(Base):
    """Auditoría: quién reabrió una hoja de numeración ya cerrada, cuándo y por qué.

    La hoja se cierra sola al confirmar/generar (candado). Reabrirla es una
    excepción (ADMIN, GERENTE_PLANTA, SUPERVISOR_CORTE, JEFE_PLANTA) y siempre
    queda con motivo — el control real está en que quede trazado, no en el rol.
    """
    __tablename__ = "of_numeracion_reaperturas"

    id         = Column(Integer, primary_key=True, index=True)
    of_id      = Column(Integer, ForeignKey("ordenes_fabricacion.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    motivo     = Column(String(300), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    of      = relationship("OrdenFabricacion")
    usuario = relationship("Usuario")
