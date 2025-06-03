from flask import Blueprint

db_bp = Blueprint('database', __name__, url_prefix='/database')

from . import routes  # Importar rutas al final para evitar importaciones circulares
