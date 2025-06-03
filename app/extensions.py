from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from elasticsearch import Elasticsearch
import logging
from flask import current_app

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
    """Obtiene una conexión a Elasticsearch"""
    try:
        if not all([current_app.config['ELASTICSEARCH_HOST'], current_app.config['ELASTICSEARCH_API_KEY']]):
            logging.error("Faltan configuraciones de Elasticsearch")
            return None
            
        client = Elasticsearch(
            current_app.config['ELASTICSEARCH_HOST'],
            api_key=current_app.config['ELASTICSEARCH_API_KEY'],
            verify_certs=True
        )
        
        if not client.ping():
            logging.error("No se pudo conectar a Elasticsearch")
            return None
            
        return client
    except Exception as e:
        logging.error(f"Error al conectar con Elasticsearch: {e}")
        return None
