# Tareas en segundo plano — regla y helper

Guía corta para cuando se agreguen `BackgroundTasks` (o hilos) al ERP. Hoy el
sistema casi no usa tareas de fondo (solo la notificación WebSocket, que ya
pasa datos primitivos). Antes de introducir la primera tarea pesada de fondo,
seguir estas reglas.

## Regla de oro: sesión de BD propia

Una tarea que corre **fuera** del ciclo request-response NO debe reutilizar la
sesión inyectada por `get_db`. Esa sesión se cierra en el `finally` de `get_db`
apenas se envía la respuesta HTTP. Si la tarea la usa después:

- errores intermitentes de `session is closed`,
- `DetachedInstanceError` al tocar atributos de objetos ORM,
- fallos difíciles de reproducir (dependen del timing de cierre).

**Nunca** hagas esto:

```python
@router.post("/x")
def endpoint(bg: BackgroundTasks, db: Session = Depends(get_db)):
    bg.add_task(mi_trabajo, db)        # ❌ db se cerrará antes de que corra
```

## Cómo hacerlo bien: `ejecutar_en_fondo`

`app/core/background.py` expone `ejecutar_en_fondo(trabajo, *args)`, que abre
una sesión **nueva**, hace commit/rollback y siempre cierra, con log del error.

```python
from app.core.background import ejecutar_en_fondo

@router.post("/x")
def endpoint(bg: BackgroundTasks, ...):
    # Pasa datos primitivos (ids/valores), NUNCA la sesión ni objetos ORM.
    bg.add_task(ejecutar_en_fondo, mi_trabajo, of_id)
    return {"status": "encolado"}

def mi_trabajo(db, of_id):
    of = db.get(OrdenFabricacion, of_id)   # sesión propia y fresca
    ...                                    # el commit lo hace ejecutar_en_fondo
```

## Qué NO pasar a la tarea

- La sesión `db` del request.
- Objetos ORM cargados en el request (quedan "detached"). Pasa **ids** y
  vuelve a cargarlos con la sesión propia dentro del trabajo.

## Límite de las BackgroundTasks nativas

`BackgroundTasks` de FastAPI corre en el mismo proceso: sirve para tareas
**ligeras y cortas** (enviar un correo, escribir un log, una notificación). Para
trabajo pesado o largo (import SAP masivo, reportes masivos) NO uses
BackgroundTasks: satura la RAM/el threadpool del server. Eso va a una cola con
worker aparte (Celery / ARQ / RQ) — ver `DESPLIEGUE_CONCURRENCIA.md` y la
Fase D del plan de tareas en segundo plano.
