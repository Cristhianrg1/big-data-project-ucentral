import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

class Config:
    # Configuración básica
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'clave_por_defecto_insegura')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    
    # MongoDB
    MONGO_URI = os.getenv('MONGO_URI')
    
    # Elasticsearch
    ELASTICSEARCH_HOST = os.getenv('ELASTICSEARCH_HOST')
    ELASTICSEARCH_API_KEY = os.getenv('ELASTICSEARCH_API_KEY')
    ELASTICSEARCH_INDEX = os.getenv('ELASTICSEARCH_INDEX', 'ucentral_test')
    
    # Versión de la aplicación
    VERSION_APP = "0.1.0"
    CREATOR_APP = "Cristhian Rodriguez"
    APP_CREATOR = "Cristhian Rodriguez"  # Para el pie de página
