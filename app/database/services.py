from datetime import datetime
from app.extensions import get_mongo_client
from bson import ObjectId
from bson.errors import InvalidId
from flask import current_app

def get_databases():
    """Obtiene la lista de bases de datos disponibles"""
    client = get_mongo_client()
    if not client:
        return []
    
    try:
        # Obtener lista de bases de datos y filtrar las del sistema y administración
        system_dbs = ['admin', 'local', 'config', 'administracion']
        databases = [db for db in client.list_database_names() if db not in system_dbs]
        return databases
    except Exception as e:
        print(f"Error al obtener bases de datos: {e}")
        return []
    finally:
        client.close()

def get_collections(database_name):
    """Obtiene las colecciones de una base de datos"""
    from flask import current_app
    
    current_app.logger.info(f'Obteniendo colecciones para la base de datos: {database_name}')
    client = get_mongo_client()
    if not client:
        current_app.logger.error('No se pudo conectar a MongoDB')
        return []
    
    try:
        current_app.logger.info(f'Listando bases de datos disponibles: {client.list_database_names()}')
        
        if database_name not in client.list_database_names():
            current_app.logger.warning(f'La base de datos {database_name} no existe')
            return []
            
        db = client[database_name]
        collection_names = db.list_collection_names()
        current_app.logger.info(f'Colecciones encontradas en {database_name}: {collection_names}')
        
        collections_info = []
        for collection_name in collection_names:
            try:
                collection = db[collection_name]
                count = collection.count_documents({})
                collections_info.append({
                    'name': collection_name,
                    'count': count
                })
                current_app.logger.debug(f'Colección procesada: {collection_name} con {count} documentos')
            except Exception as e:
                current_app.logger.error(f'Error al procesar la colección {collection_name}: {str(e)}')
                continue
                
        current_app.logger.info(f'Se encontraron {len(collections_info)} colecciones')
        return collections_info
        
    except Exception as e:
        current_app.logger.error(f'Error en get_collections: {str(e)}', exc_info=True)
        return []
    finally:
        try:
            client.close()
        except Exception as e:
            current_app.logger.error(f'Error al cerrar la conexión: {str(e)}')

def get_documents(database_name, collection_name, page=1, per_page=10):
    """Obtiene documentos de una colección con paginación"""
    client = get_mongo_client()
    if not client:
        return [], 0
    
    try:
        db = client[database_name]
        collection = db[collection_name]
        
        # Contar total de documentos
        total = collection.count_documents({})
        
        # Obtener documentos con paginación
        skip = (page - 1) * per_page
        cursor = collection.find().skip(skip).limit(per_page)
        
        # Convertir ObjectId a string para serialización JSON
        documents = []
        for doc in cursor:
            doc['_id'] = str(doc['_id'])
            documents.append(doc)
            
        return documents, total
    except Exception as e:
        current_app.logger.error(f"Error al obtener documentos: {e}")
        return [], 0
    finally:
        client.close()

def create_database(database_name):
    """Crear una nueva base de datos"""
    client = get_mongo_client()
    if not client:
        return False, "Error al conectar con MongoDB"
    
    try:
        # Verificar si la base de datos ya existe
        if database_name in client.list_database_names():
            return False, f"La base de datos '{database_name}' ya existe"
        
        # Crear una colección para inicializar la base de datos
        db = client[database_name]
        db['inicializacion'].insert_one({'status': 'ok'})
        return True, f"Base de datos '{database_name}' creada exitosamente"
        
    except Exception as e:
        error_msg = f"Error al crear la base de datos: {str(e)}"
        current_app.logger.error(error_msg)
        return False, error_msg
    finally:
        client.close()

def collection_exists(database_name, collection_name):
    """Verificar si una colección existe en una base de datos"""
    client = get_mongo_client()
    if not client:
        return False
    
    try:
        db = client[database_name]
        return collection_name in db.list_collection_names()
    except Exception as e:
        current_app.logger.error(f"Error al verificar colección {database_name}.{collection_name}: {e}")
        return False
    finally:
        client.close()

def create_collection(database_name, collection_name):
    """Crear una nueva colección en una base de datos"""
    client = get_mongo_client()
    if not client:
        return False, "Error al conectar con MongoDB"
    
    try:
        # Verificar si la base de datos existe
        if database_name not in client.list_database_names():
            return False, f"La base de datos '{database_name}' no existe"
        
        db = client[database_name]
        
        # Verificar si la colección ya existe
        if collection_name in db.list_collection_names():
            return False, f"La colección '{collection_name}' ya existe"
        
        # Crear la colección insertando un documento vacío
        db[collection_name].insert_one({})
        return True, f"Colección '{collection_name}' creada exitosamente"
        
    except Exception as e:
        error_msg = f"Error al crear la colección: {str(e)}"
        current_app.logger.error(error_msg)
        return False, error_msg
    finally:
        client.close()

def get_document(database_name, collection_name, document_id):
    """Obtener un documento por su ID"""
    client = get_mongo_client()
    if not client:
        return None
    
    try:
        db = client[database_name]
        collection = db[collection_name]
        
        # Convertir el ID de string a ObjectId
        try:
            obj_id = ObjectId(document_id)
        except (InvalidId, TypeError):
            return None
        
        # Obtener el documento
        document = collection.find_one({'_id': obj_id})
        if document:
            # Convertir ObjectId a string para serialización
            document['_id'] = str(document['_id'])
        return document
        
    except Exception as e:
        current_app.logger.error(f"Error al obtener documento: {str(e)}")
        return None
    finally:
        client.close()

def insert_document(database_name, collection_name, document_data):
    """Insertar un nuevo documento en la colección"""
    client = get_mongo_client()
    if not client:
        return False, "Error al conectar con MongoDB"
    
    try:
        db = client[database_name]
        collection = db[collection_name]
        
        # Procesar campos especiales
        processed_data = process_document_data(document_data)
        
        # Insertar el documento
        result = collection.insert_one(processed_data)
        
        if result.inserted_id:
            return True, str(result.inserted_id)
        return False, "No se pudo insertar el documento"
        
    except Exception as e:
        error_msg = f"Error al insertar documento: {str(e)}"
        current_app.logger.error(error_msg)
        return False, error_msg
    finally:
        client.close()

def insert_many_documents(database_name, collection_name, documents, batch_size=100):
    """Insertar múltiples documentos en la colección en lotes
    
    Args:
        database_name: Nombre de la base de datos
        collection_name: Nombre de la colección
        documents: Lista de documentos a insertar
        batch_size: Tamaño del lote para la inserción (predeterminado: 100)
        
    Returns:
        tuple: (éxito, mensaje) o (éxito, resultado)
    """
    client = get_mongo_client()
    if not client:
        return False, "Error al conectar con MongoDB"
    
    try:
        db = client[database_name]
        collection = db[collection_name]
        
        total_docs = len(documents)
        inserted_count = 0
        errors = []
        
        current_app.logger.info(f'Iniciando inserción de {total_docs} documentos en lotes de {batch_size}')
        
        # Procesar en lotes
        for i in range(0, total_docs, batch_size):
            batch = documents[i:i + batch_size]
            processed_batch = []
            
            # Procesar cada documento del lote
            for doc in batch:
                try:
                    processed_doc = process_document_data(doc)
                    processed_batch.append(processed_doc)
                except Exception as e:
                    error_msg = f"Error procesando documento: {str(e)}"
                    current_app.logger.warning(error_msg)
                    errors.append(error_msg)
                    continue
            
            # Insertar el lote si hay documentos válidos
            if processed_batch:
                try:
                    result = collection.insert_many(processed_batch, ordered=False)
                    inserted_count += len(result.inserted_ids)
                    current_app.logger.info(f'Lote insertado: {len(result.inserted_ids)} documentos (total: {inserted_count}/{total_docs})')
                except Exception as e:
                    error_msg = f"Error insertando lote: {str(e)}"
                    current_app.logger.error(error_msg)
                    errors.append(error_msg)
                    # Continuar con el siguiente lote a pesar del error
                    continue
        
        # Preparar mensaje de resultado
        if errors:
            msg = f"Se insertaron {inserted_count} de {total_docs} documentos. {len(errors)} errores. Primer error: {errors[0]}"
            if inserted_count > 0:
                current_app.logger.warning(msg)
                return True, msg  # Consideramos éxito parcial
            else:
                current_app.logger.error(msg)
                return False, msg
        
        success_msg = f"Se insertaron exitosamente {inserted_count} documentos"
        current_app.logger.info(success_msg)
        return True, success_msg
        
    except Exception as e:
        error_msg = f"Error al insertar documentos: {str(e)}"
        current_app.logger.error(error_msg, exc_info=True)
        return False, error_msg
    finally:
        client.close()

def update_document(database_name, collection_name, document_id, update_data):
    """Actualizar un documento existente"""
    client = get_mongo_client()
    if not client:
        return False, "Error al conectar con MongoDB"
    
    try:
        db = client[database_name]
        collection = db[collection_name]
        
        # Convertir el ID de string a ObjectId
        try:
            obj_id = ObjectId(document_id)
        except (InvalidId, TypeError):
            return False, "ID de documento no válido"
        
        # Procesar campos especiales
        processed_data = process_document_data(update_data)
        
        # Eliminar _id si está presente para evitar errores de actualización
        if '_id' in processed_data:
            del processed_data['_id']
        
        # Actualizar el documento
        result = collection.update_one(
            {'_id': obj_id},
            {'$set': processed_data}
        )
        
        if result.matched_count == 0:
            return False, "Documento no encontrado"
            
        return True, "Documento actualizado exitosamente"
        
    except Exception as e:
        error_msg = f"Error al actualizar documento: {str(e)}"
        current_app.logger.error(error_msg)
        return False, error_msg
    finally:
        client.close()

def delete_document(database_name, collection_name, document_id):
    """Eliminar un documento de una colección"""
    client = get_mongo_client()
    if not client:
        return False, "Error al conectar con MongoDB"
    
    try:
        db = client[database_name]
        collection = db[collection_name]
        
        # Convertir el ID de string a ObjectId
        try:
            obj_id = ObjectId(document_id)
        except (InvalidId, TypeError):
            return False, "ID de documento no válido"
        
        # Eliminar el documento
        result = collection.delete_one({'_id': obj_id})
        
        if result.deleted_count == 0:
            return False, "Documento no encontrado"
            
        return True, "Documento eliminado exitosamente"
        
    except Exception as e:
        error_msg = f"Error al eliminar el documento: {str(e)}"
        current_app.logger.error(error_msg)
        return False, error_msg
    finally:
        client.close()

def process_document_data(data):
    """Procesar los datos del documento antes de insertar/actualizar"""
    if not isinstance(data, dict):
        return data
    
    processed = {}
    for key, value in data.items():
        # Procesar campos anidados
        if isinstance(value, dict):
            # Manejar campos especiales como _id, createdAt, etc.
            if key == '_id' and '$oid' in value:
                try:
                    processed[key] = ObjectId(value['$oid'])
                    continue
                except (InvalidId, TypeError):
                    pass
            elif key in ['createdAt', 'updatedAt'] and '$date' in value:
                try:
                    processed[key] = value['$date']
                    continue
                except (ValueError, TypeError):
                    pass
            # Procesar objetos anidados recursivamente
            processed[key] = process_document_data(value)
        # Procesar arrays
        elif isinstance(value, list):
            processed[key] = [process_document_data(item) for item in value]
        else:
            processed[key] = value
    
    # Agregar marcas de tiempo si no existen
    if 'createdAt' not in processed:
        processed['createdAt'] = {'$date': datetime.utcnow().isoformat() + 'Z'}
    processed['updatedAt'] = {'$date': datetime.utcnow().isoformat() + 'Z'}
    
    return processed
