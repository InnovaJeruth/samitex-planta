# Plan de trabajo — Externalizar CSS/JS y ordenar uploads

_Análisis + plan. No se programa hasta aprobar. Objetivo: (A) sacar el CSS/JS común
a archivos servidos con caché, y (B) sacar los uploads de `static/` para que no sean
públicos. Todo por fases, con verificación entre cada una._

## Situación actual (verificada)

- **CSS/JS:** todo **inline** en las plantillas (`base.html` + cada página). Cero
  referencias a `/static/` para estilos/scripts. `static/css` y `static/js` vacías.
- **Uploads:** el `catalogo` guarda en `static/uploads/{prendas,piezas,docs_prenda}` →
  **servidos públicamente** por `StaticFiles` en `/static/...`. Las plantillas los
  referencian directo: `<img src="/{{ imagen_ruta }}">` y `<a href="/{{ ruta_archivo }}">`.
- En cambio, **OF y curvas** ya sirven sus documentos por **endpoints con rol**
  (`/of/api/documentos/{id}/descargar`, `/curvas/api/curvas/{id}/descargar`) desde
  `settings.UPLOAD_DIR = "uploads"` (privado). El **catálogo es el outlier**.

---

## PARTE A — Externalizar CSS/JS común

**Restricción clave:** el JS por página que usa variables Jinja (`{{ ...|tojson }}`,
p. ej. `TALLAJES`, `REQ_ID`) **no puede** moverse a un `.js` estático (no hay
templating en archivos estáticos). Solo se externaliza el código **compartido y sin
Jinja**.

- **A1 · CSS global → `static/css/app.css`** *(riesgo bajo)*
  Mover el `<style>` global de `base.html` (nav, layout, toasts, tipografía) a
  `static/css/app.css` y enlazar con `<link rel="stylesheet" href="/static/css/app.css?v=1">`.
  Verificación: revisión visual de 4–5 vistas representativas.

- **A2 · JS global → `static/js/app.js`** *(riesgo bajo)*
  Mover los helpers compartidos de `base.html` (`apiFetch`, `toast`/`showToast`,
  CSRF, nav móvil) a `static/js/app.js` con `<script src="/static/js/app.js?v=1">`.
  Estos no usan variables Jinja (el CSRF se lee de cookie) → seguros de mover.
  El JS específico de cada página **se queda inline**.

- **A3 · Dedupe de estilos de componentes** *(incremental, cosmético)*
  Estilos repetidos entre plantillas (`.btn`, `.pm-card`, tablas, chips) → consolidar
  en `app.css` y quitarlos de cada página. Se hace **por página**, con revisión visual,
  para controlar especificidad/orden.

- **Caché:** `StaticFiles` ya envía cabeceras de caché; usar `?v=<n>` en los enlaces
  para forzar recarga tras cada deploy.

**Beneficio:** caché de navegador (CSS/JS no se reenvía en cada página), menos
duplicación, mantenimiento centralizado. **Riesgo:** solo visual (orden/especificidad);
sin impacto en backend ni tests. Validación = revisión en pantalla.

---

## PARTE B — Sacar uploads de `static/` (privacidad)

**B1 · Documentos de catálogo (prioridad — son sensibles: fichas técnicas / HDC)** *(riesgo medio)*
1. Cambiar `UPLOAD_DOCS` de `static/uploads/docs_prenda` → `uploads/catalogo/docs`
   (bajo `settings.UPLOAD_DIR`, fuera de `static/`).
2. Crear endpoint **con rol** `GET /catalogo/api/documentos/{doc_id}/descargar`
   (`FileResponse` + `ROLES_...`), reutilizando el patrón de `of.py`.
3. Cambiar en las plantillas el `<a href="/{{ doc.ruta_archivo }}">` por el endpoint
   `/catalogo/api/documentos/{{ doc.id }}/descargar`.
4. **Migración de datos:** script idempotente que mueve los archivos físicos existentes
   de `static/uploads/docs_prenda/` a la nueva ruta y actualiza `prenda_documentos.ruta_archivo`
   en la BD. Backup previo.

**B2 · Imágenes de prenda/pieza** *(baja prioridad — son fotos, no sensibles)*
- Opción recomendada: **dejarlas en `static/`**. Son fotos de producto, sin dato
  confidencial; moverlas obliga a crear un endpoint de imagen y a cambiar **todos** los
  `<img src>` (varias plantillas) → mucho trabajo para poco valor.
- Opción alternativa (si se decide que las fotos también son privadas): endpoint
  `GET /catalogo/api/imagen/{tipo}/{id}` + cambiar los `<img src>`. Más costoso.

**Beneficio B1:** los documentos técnicos dejan de ser accesibles por URL directa sin
auth. **Riesgo:** medio — toca almacenamiento + BD (rutas) + plantillas + migración de
archivos existentes. Reversible con el backup.

---

## Orden sugerido y verificación

| Fase | Qué | Riesgo | Verificación |
|------|-----|--------|--------------|
| 1 | A1 (CSS global) | Bajo | Visual (5 vistas) |
| 2 | A2 (JS global) | Bajo | Visual + funcional (login, toasts, fetch) |
| 3 | B1 (docs catálogo → privado + endpoint + migración) | Medio | `pytest` + descarga con/sin rol + verificar migración |
| 4 | A3 (dedupe estilos por página) | Bajo | Visual incremental |
| 5 | B2 (imágenes) | — | Opcional; solo si se decide privatizar fotos |

**Regla:** cada fase se entrega, se corre `pytest` (backend) + revisión visual (frontend),
y recién se pasa a la siguiente. B1 lleva backup de `static/uploads/docs_prenda` antes de migrar.

---

## Fuera de alcance / notas

- No se cambia el flujo de OF/curvas (ya privados y correctos).
- `static/fichas_ingenieria.html` parece un archivo suelto/resto → revisar si se elimina.
- A y B son independientes: se pueden hacer en cualquier orden; A es más seguro para empezar.
