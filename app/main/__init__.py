from flask import Blueprint

main_bp = Blueprint('main', __name__)

from . import routes  # Importar rutas al final para evitar importaciones circulares
