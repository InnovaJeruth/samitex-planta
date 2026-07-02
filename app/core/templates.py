"""
Singleton de Jinja2Templates para toda la aplicación.

Importar desde aquí en lugar de instanciar Jinja2Templates en cada router:

    from app.core.templates import templates
"""
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates", auto_reload=True)


def _media_url(path: str) -> str:
    """URL correcta para un archivo: absoluta si es Supabase (http...), relativa si es local."""
    if not path:
        return ""
    return path if path.startswith("http") else f"/{path}"


templates.env.filters["media_url"] = _media_url
