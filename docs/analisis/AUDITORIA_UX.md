# Auditoría de Usabilidad (UX/UI) — SAMITEX-PLANTA

Evaluación heurística del front-end SSR (Jinja2), estructura de vistas y flujos.
Alcance: `app/templates/*`, `static/fichas_ingenieria.html`, routers y capa WebSocket.

**Veredicto general:** la base de UI es sólida y cuidada (sistema de toasts, modal de
confirmación, CSRF automático, `focus-visible`, skip-link, nav responsive, panel de gates
muy claro). Los problemas no son estéticos sino de **flujo, consistencia de data-entry y una
promesa de "tiempo real" que hoy no se cumple**. Detalle abajo.

---

## 1) Carga cognitiva y navegación por roles

**Lo que está bien**
- El nav (`base.html`, líneas 315–344) filtra destinos por rol con `{% if rol in [...] %}`.
  Un `LOGISTICA` no ve "Catálogo" ni "Admin"; un `COMERCIAL` no ve "Plantas". Correcto.
- El panel de gates en `of/detalle.html` segmenta los documentos "por gate con permisos por
  rol" (`gates_permitidos`, `es_rol_doc`), y hasta cuenta "mis gates" por rol. Buen patrón.

**Problemas**
- **Roles sin puerta de entrada.** El nav solo expone ~7 destinos. Roles operativos clave
  —`INGENIERIA`, `CALIDAD`, `LOGISTICA`— no tienen un enlace propio y aterrizan en Dashboard
  u Órdenes sin saber a dónde ir. En particular, las **fichas de ingeniería** viven en un HTML
  suelto (`static/fichas_ingenieria.html`, servido en `/ing/fichas`) que **no está enlazado en
  ningún lado del nav**. Un ingeniero no llega a su herramienta salvo que sepa la URL.
- **El flujo de las 9 fases exige demasiado salto de contexto.** El corte de tela (F1–F3) se
  opera en una pantalla (`of/trazos.html`, "Armar placas") y la confección (F4–F7) en otra
  (`corte/seguimiento.html`). Son dos URLs, dos modelos mentales (placas vs. pieza×talla) y no
  hay una "cinta" de progreso global que muestre en qué fase va la OF completa ni un botón
  "siguiente paso". El supervisor debe recordar el orden `F1→F2→F3→F4→F8→F9→F5→F6→F7`.
- **La grilla de seguimiento muestra todas las fases a todos.** No se adapta al rol: Calidad ve
  columnas de Tizado/Tendido y viceversa. Aumenta ruido visual para tareas que no son suyas.

---

## 2) Prevención de errores en carga de datos (data-entry)

**Lo bueno — armador de placas (`of/trazos.html`)**
- Validación cliente de verdad: `preview()` (líneas 169–184) recalcula en vivo prendas =
  capas×veces y metros, y **bloquea antes de enviar** cuando `capas > MAXCAPAS` (tope de
  máquina) o cuando `capas×veces > restante` de la talla (exceso sobre el pedido).
- `crearPlaca()` (188–201) re-valida todo y muestra el error **inline** en `#crear-msg`, sin
  perder lo tipeado. Los inputs son `type="number" min="1"`. Este módulo es el estándar a imitar.

**Problemas**
- **Inconsistencia grave de entrada numérica en Seguimiento.** El registro de avance por talla
  usa `prompt('Cantidad a registrar (piezas):')` (`seguimiento.html` línea 479) y confirma con
  `confirm(...)` nativo (480). El `prompt` no valida rango, no muestra el máximo permitido, no
  respeta el estilo, y en móvil/tablet de planta es incómodo. El tope real recién se valida en
  el servidor → el operario tipea, envía, y recién ahí ve el rechazo (toast de error).
- **Doble estándar de diálogos.** `base.html` ya provee `showConfirm()` (modal estilizado) y
  `showToast()`, pero `seguimiento.html` y `trazos.html` siguen usando `confirm()`/`prompt()`
  nativos (p. ej. `tendido()` y `borrar()` en trazos, líneas 208 y 214). Rompe la coherencia y
  la confianza.
- **La regla "no dos colores en la misma mesa" es invisible.** Se cumple por diseño (1 OF = 1
  variante = 1 color), pero la pantalla de placas **no muestra el color/tela de la OF** en
  ningún lado, así que el operario no tiene confirmación visual de qué está tendiendo.
- **Feedback de error es solo un toast efímero (4 s).** Para un rechazo de negocio ("excede el
  pedido en talla M") el mensaje desaparece y no queda anclado al campo que lo causó.

---

## 3) Manejo de estados y "tiempo real" (WebSockets)

**Hallazgo crítico: el tiempo real no existe hoy — es código muerto.**
- El backend registra el router WS (`app/main.py` → `/ws/of/{of_numero}`) y tiene un
  `WebSocketManager` con `connect/disconnect/broadcast/broadcast_of`.
- **Pero nadie llama `broadcast`** (búsqueda en todo `app/**.py`: cero llamadas fuera del propio
  manager) y **ningún template abre un cliente** (`new WebSocket` no aparece en `app/` ni en
  `static/`). El canal existe, nunca emite y nadie escucha.
- Lo que sí ocurre: `seguimiento.html` hace `refreshTalla()` (línea 472) que re-consulta
  `/corte/api/{of}/estado-talla` **solo después de la propia acción del usuario**. Es un
  *pull* post-acción, no un *push* en vivo.

**Impacto UX**
- Dos supervisores en la misma OF **no ven** los cambios del otro hasta recargar manualmente.
  En una planta con varias estaciones esto genera datos pisados y desconfianza en la tabla.
- La UI **promete** algo que no entrega: no hay indicador de "conectado/actualizado hace X",
  ni animación cuando entra un cambio, ni sello de hora. El usuario no sabe si lo que ve es de
  hace 2 segundos o de hace 2 horas.

**Decisión requerida:** o se **conecta** el WS de verdad (backend hace `broadcast_of` al
registrar avance/completar/tendido; front se suscribe y refresca la fila afectada), o se
**elimina** la capa WS y se documenta que la actualización es por recarga. Mantenerla a medias
es lo peor de los dos mundos.

---

## 4) Plan de refactorización accionable (priorizado)

**P0 — Cerrar la brecha de "tiempo real" (elige una vía)**
- **Vía A (recomendada):** en `corte_service`/`trazo_service`, tras `registrar_avance`,
  `completar_fase`, `registrar_tendido`, `marcar_corte`, llamar
  `await ws_manager.broadcast_of(of.numero_of, "avance", {...})`. En `seguimiento.html` y
  `trazos.html` abrir `new WebSocket(\`ws://.../ws/of/${OF_NUMERO}\`)`, y al recibir un mensaje
  ejecutar el `refreshTalla()`/`load()` que ya existen + resaltar la fila cambiada + sello
  "actualizado hace un momento".
- **Vía B (si no hay tiempo):** quitar `ws.router` y `websocket_manager`, y agregar un
  `setInterval` de *polling* cada N s con indicador visible de "última actualización".

**P1 — Unificar data-entry (reemplazar `prompt`/`confirm` nativos)**
- Sustituir el `prompt()` de avance (`seguimiento.html:479`) y de tendido (`trazos.html:208`)
  por un **mini-modal numérico** que muestre el **máximo permitido** ("máx. 40 restantes") y
  valide `1..restante` en cliente antes de enviar.
- Sustituir todos los `confirm()` por el `showConfirm()` que ya está en `base.html`.
- Anclar el error de negocio junto al control (no solo toast): mantener el patrón `#crear-msg`
  de trazos como estándar en Seguimiento.

**P2 — Reducir carga cognitiva de las 9 fases**
- Añadir en `of/detalle.html` (y como encabezado de Seguimiento/Trazos) una **cinta única de
  fases F1→F7** con estado y un botón "Continuar en la fase actual" que lleve directo a la
  pantalla correcta (placas si F1–F3, grilla si F4–F7). Elimina el salto manual entre URLs.
- En `seguimiento.html` `renderTabla()`, **filtrar las columnas de fase por el rol** (Calidad
  ve F6; Corte ve F1–F3), para que cada quien vea solo lo suyo.

**P3 — Navegación por rol completa**
- Agregar al nav de `base.html` entradas para los roles operativos que hoy no tienen puerta:
  enlace **"Ingeniería"** (`/ing/fichas`) visible para `INGENIERIA`/`CALIDAD`/`ADMIN`, y revisar
  que cada uno de los 14 roles tenga al menos un destino inicial claro.

**P4 — Contexto visible en placas**
- Mostrar en `of/trazos.html` un encabezado con **variante + color de tela** de la OF, para dar
  el refuerzo visual de "qué tela va en la mesa" (soporta la regla de no mezclar colores).

**P5 — Consistencia menor**
- Migrar la ficha de ingeniería (`static/fichas_ingenieria.html`, hoy HTML plano fuera del
  layout) a una plantilla que **extienda `base.html`**, para que herede nav, toasts, CSRF y
  estilos, en vez de vivir aislada.
