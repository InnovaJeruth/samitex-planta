"""
Singleton de Jinja2Templates para toda la aplicación.

Importar desde aquí en lugar de instanciar Jinja2Templates en cada router:

    from app.core.templates import templates
"""
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates", auto_reload=True)
