from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from elasticsearch import Elasticsearch
import logging
from functools import wraps
from flask import current_app, jsonify, render_template, request

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')
    ]
)

def get_mongo_client():
    """Obtiene una conexión a MongoDB"""
    try:
        if not current_app.config['MONGO_URI']:
            logging.error("MONGO_URI no está configurada")
            return None
            
        client = MongoClient(
            current_app.config['MONGO_URI'],
            server_api=ServerApi('1'),
            connectTimeoutMS=5000,
            socketTimeoutMS=30000,
            serverSelectionTimeoutMS=5000
        )
        
        # Verificar la conexión
        client.admin.command('ping')
        logging.info("Conexión exitosa a MongoDB!")
        return client
    except Exception as e:
        logging.error(f"Error al conectar a MongoDB: {e}")
        return None

def get_elasticsearch_client():
    """
    Obtiene una conexión a Elasticsearch con manejo de errores mejorado.
    
    Returns:
        Elasticsearch: Cliente de Elasticsearch si la conexión es exitosa.
        None: Si hay algún error en la configuración o conexión.
    """
    try:
        # Verificar que las configuraciones requeridas estén presentes
        if not current_app.config.get('ELASTICSEARCH_HOST'):
            logging.error("ELASTICSEARCH_HOST no está configurado en las variables de entorno")
            return None
            
        if not current_app.config.get('ELASTICSEARCH_API_KEY'):
            logging.error("ELASTICSEARCH_API_KEY no está configurado en las variables de entorno")
            return None
            
        # Configurar el cliente con timeouts apropiados
        client = Elasticsearch(
            current_app.config['ELASTICSEARCH_HOST'],
            api_key=current_app.config['ELASTICSEARCH_API_KEY'],
            verify_certs=True,
            request_timeout=10,  # 10 segundos de timeout
            max_retries=1,       # Número de reintentos
            retry_on_timeout=False
        )
        
        # Verificar la conexión con un ping
        if not client.ping():
            logging.error("No se pudo conectar a Elasticsearch: Ping fallido")
            return None
            
        logging.info("Conexión exitosa a Elasticsearch")
        return client
        
    except Exception as e:
        logging.error(f"Error al conectar con Elasticsearch: {str(e)}", exc_info=True)
        return None

def requires_elasticsearch(f):
    """
    Decorador para manejar rutas que requieren Elasticsearch.
    Si Elasticsearch no está disponible, muestra un mensaje de error apropiado.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Verificar si Elasticsearch está configurado y disponible
        es_client = get_elasticsearch_client()
        
        if es_client is None:
            # Si es una petición AJAX, devolver un JSON de error
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': False,
                    'error': 'El servicio de búsqueda no está disponible en este momento. Por favor, intente más tarde.'
                }), 503
            
            # Si es una petición normal, renderizar una plantilla de error
            return render_template(
                'error.html',
                error_code=503,
                error_message='Servicio de búsqueda no disponible',
                error_description='El servicio de búsqueda no está disponible en este momento. Por favor, intente más tarde.',
                version=current_app.config.get('VERSION_APP', '1.0.0')
            ), 503
            
        # Pasar el cliente de Elasticsearch como argumento adicional
        kwargs['es_client'] = es_client
        return f(*args, **kwargs)
    
    return decorated_function
