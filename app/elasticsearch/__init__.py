from flask import Blueprint

# Crear blueprint con nombre 'elastic' para ser referenciado en las plantillas
# El prefijo de URL se define en app/__init__.py cuando se registra el blueprint
elastic_bp = Blueprint('elastic', __name__)

# Importar rutas después de crear el blueprint para evitar importaciones circulares
# Importamos las rutas para que se registren con el blueprint
from . import routes  # noqa
