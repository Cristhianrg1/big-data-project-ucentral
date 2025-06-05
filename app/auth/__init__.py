from flask import Blueprint

auth_bp = Blueprint('auth', __name__)

from . import routes  # Importar rutas al final para evitar importaciones circulares
