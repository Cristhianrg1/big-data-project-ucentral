from flask import render_template, request, redirect, url_for, session, jsonify, flash, current_app, abort
import os
import zipfile
import json
import logging
from datetime import datetime
import tempfile
import shutil
from functools import wraps
from datetime import datetime
from bson import ObjectId
from app.extensions import get_elasticsearch_client
from . import elastic_bp

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario' not in session:
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# Configurar logging
logger = logging.getLogger(__name__)

def get_index_name():
    """Obtener el nombre del índice desde la configuración"""
    return current_app.config.get('ELASTICSEARCH_INDEX', 'documentos')

@elastic_bp.route('/admin')
@login_required
def admin():
    """Panel de administración de Elasticsearch"""
    es = get_elasticsearch_client()
    if not es:
        return render_template('error.html', 
                           error_message='No se pudo conectar a Elasticsearch. Por favor, verifica la configuración.',
                           status_code=503), 503
    
    try:
        # Obtener información del índice
        index_name = get_index_name()
        index_info = es.indices.get(index=index_name, ignore=[404])
        
        if 'error' in index_info and index_info['status'] == 404:
            return render_template('elastic/admin.html',
                               index_name=index_name,
                               index_exists=False,
                               doc_count=0)
        
        # Obtener conteo de documentos
        doc_count = es.count(index=index_name)['count']
        
        return render_template('elastic/admin.html',
                           index_name=index_name,
                           index_exists=True,
                           doc_count=doc_count)
    except Exception as e:
        logger.error(f'Error en admin de Elasticsearch: {str(e)}')
        return render_template('error.html', 
                           error_message=f'Error al conectar con Elasticsearch: {str(e)}',
                           status_code=500), 500

@elastic_bp.route('/crear-indice', methods=['POST'])
@login_required
def crear_indice():
    """Crear un nuevo índice en Elasticsearch"""
    es = get_elasticsearch_client()
    if not es:
        return jsonify({'success': False, 'error': 'No se pudo conectar a Elasticsearch'}), 503
    
    try:
        index_name = get_index_name()
        
        # Verificar si el índice ya existe
        if es.indices.exists(index=index_name):
            # Eliminar el índice existente
            es.indices.delete(index=index_name)
        
        # Crear un nuevo índice con mapeo básico
        es.indices.create(index=index_name, body={
            'settings': {
                'number_of_shards': 1,
                'number_of_replicas': 0
            },
            'mappings': {
                'properties': {
                    'titulo': {'type': 'text'},
                    'contenido': {'type': 'text'},
                    'fecha_creacion': {'type': 'date'},
                    'usuario': {'type': 'keyword'}
                }
            }
        })
        
        logger.info(f'Índice {index_name} creado exitosamente')
        return jsonify({
            'success': True,
            'message': f'Índice {index_name} creado exitosamente'
        })
        
    except Exception as e:
        logger.error(f'Error al crear índice: {str(e)}')
        return jsonify({
            'success': False, 
            'error': f'Error al crear el índice: {str(e)}'
        }), 500

@elastic_bp.route('/eliminar-indice', methods=['DELETE'])
@login_required
def eliminar_indice():
    """Eliminar el índice de Elasticsearch"""
    es = get_elasticsearch_client()
    if not es:
        return jsonify({'success': False, 'error': 'No se pudo conectar a Elasticsearch'}), 503
    
    try:
        index_name = get_index_name()
        
        # Verificar si el índice existe
        if not es.indices.exists(index=index_name):
            return jsonify({
                'success': False, 
                'error': f'El índice {index_name} no existe'
            }), 404
        
        # Eliminar el índice
        es.indices.delete(index=index_name)
        logger.info(f'Índice {index_name} eliminado exitosamente')
        
        return jsonify({
            'success': True,
            'message': f'Índice {index_name} eliminado exitosamente'
        })
        
    except Exception as e:
        logger.error(f'Error al eliminar índice: {str(e)}')
        return jsonify({
            'success': False, 
            'error': f'Error al eliminar el índice: {str(e)}'
        }), 500

@elastic_bp.route('/agregar-documentos', methods=['GET', 'POST'])
@login_required
def agregar_documentos():
    """Agregar documentos a Elasticsearch desde archivos JSON o ZIP"""
    if request.method == 'POST':
        if 'archivo' not in request.files:
            flash('No se ha seleccionado ningún archivo', 'error')
            return redirect(request.url)
        
        archivo = request.files['archivo']
        if archivo.filename == '':
            flash('No se ha seleccionado ningún archivo', 'error')
            return redirect(request.url)
        
        es = get_elasticsearch_client()
        if not es:
            flash('No se pudo conectar a Elasticsearch', 'error')
            return redirect(request.url)
        
        try:
            # Crear directorio temporal
            import tempfile
            import shutil
            
            temp_dir = tempfile.mkdtemp()
            temp_file = os.path.join(temp_dir, archivo.filename)
            archivo.save(temp_file)
            
            success_count = 0
            error_count = 0
            index_name = get_index_name()
            
            # Verificar si es un ZIP
            if archivo.filename.lower().endswith('.zip'):
                with zipfile.ZipFile(temp_file, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                
                # Procesar archivos JSON extraídos
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        if file.lower().endswith('.json'):
                            file_path = os.path.join(root, file)
                            try:
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    data = json.load(f)
                                    if isinstance(data, list):
                                        for doc in data:
                                            if not doc.get('fecha_publicacion'):
                                                doc['fecha_publicacion'] = datetime.now().strftime('%Y-%m-%d')
                                            es.index(index=index_name, document=doc)
                                            success_count += 1
                                    else:
                                        if not data.get('fecha_publicacion'):
                                            data['fecha_publicacion'] = datetime.now().strftime('%Y-%m-%d')
                                        es.index(index=index_name, document=data)
                                        success_count += 1
                            except Exception as e:
                                logger.error(f'Error procesando {file}: {str(e)}')
                                error_count += 1
            else:
                # Procesar archivo JSON individual
                try:
                    with open(temp_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            for doc in data:
                                if not doc.get('fecha_publicacion'):
                                    doc['fecha_publicacion'] = datetime.now().strftime('%Y-%m-%d')
                                es.index(index=index_name, document=doc)
                                success_count += 1
                        else:
                            if not data.get('fecha_publicacion'):
                                data['fecha_publicacion'] = datetime.now().strftime('%Y-%m-%d')
                            es.index(index=index_name, document=data)
                            success_count += 1
                except Exception as e:
                    logger.error(f'Error procesando archivo: {str(e)}')
                    error_count += 1
            
            # Limpiar archivos temporales
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            flash(f'Se indexaron {success_count} documentos exitosamente. Errores: {error_count}', 'success')
            return redirect(url_for('elastic.admin'))
            
        except Exception as e:
            logger.error(f'Error en agregar_documentos: {str(e)}')
            flash(f'Error al procesar el archivo: {str(e)}', 'error')
            return redirect(request.url)
    
    return render_template('elastic/agregar_documentos.html')

@elastic_bp.route('/listar-documentos')
@login_required
def listar_documentos():
    """Listar documentos en el índice de Elasticsearch"""
    es = get_elasticsearch_client()
    if not es:
        return render_template('error.html', 
                           error_message='No se pudo conectar a Elasticsearch. Por favor, verifica la configuración.',
                           status_code=503), 503
    
    try:
        index_name = get_index_name()
        
        # Verificar si el índice existe
        if not es.indices.exists(index=index_name):
            return render_template('elastic/listar_documentos.html',
                               documents=[],
                               total=0,
                               index_name=index_name)
        
        # Obtener los primeros 100 documentos
        response = es.search(
            index=index_name,
            body={
                "query": {"match_all": {}},
                "size": 100,
                "sort": [{"_score": "desc"}]
            }
        )
        
        documents = response['hits']['hits']
        total = response['hits']['total']['value']
        
        return render_template('elastic/listar_documentos.html',
                           documents=documents,
                           total=total,
                           index_name=index_name)
    except Exception as e:
        logger.error(f'Error en listar_documentos: {str(e)}')
        return render_template('error.html', 
                           error_message=f'Error al obtener documentos: {str(e)}',
                           status_code=500), 500

@elastic_bp.route('/documento/<doc_id>')
@login_required
def ver_documento(doc_id):
    """Mostrar un documento específico por su ID en una página dedicada"""
    es = get_elasticsearch_client()
    if not es:
        flash('No se pudo conectar a Elasticsearch', 'error')
        return redirect(url_for('elastic.admin'))
    
    try:
        index_name = get_index_name()
        
        # Verificar si el índice existe
        if not es.indices.exists(index=index_name):
            flash(f'El índice {index_name} no existe', 'error')
            return redirect(url_for('elastic.admin'))
        
        # Obtener el documento
        try:
            doc = es.get(index=index_name, id=doc_id)
            return render_template('elastic/ver_documento.html',
                               documento=doc['_source'],
                               doc_id=doc_id,
                               index_name=index_name)
        except Exception as e:
            if getattr(e, 'status_code', 500) == 404:
                flash('Documento no encontrado', 'error')
            else:
                logger.error(f'Error al obtener documento {doc_id}: {str(e)}')
                flash('Error al cargar el documento', 'error')
            return redirect(url_for('elastic.listar_documentos'))
            
    except Exception as e:
        logger.error(f'Error en ver_documento: {str(e)}')
        flash('Ocurrió un error al cargar el documento', 'error')
        return redirect(url_for('elastic.listar_documentos'))

@elastic_bp.route('/elastic-eliminar-documento', methods=['POST'])
@login_required
def eliminar_documento():
    try:
        logger.info('Solicitud de eliminación de documento recibida')
        
        # Obtener datos del formulario
        doc_id = request.form.get('doc_id')
        logger.info(f'ID de documento recibido: {doc_id}')
        
        if not doc_id:
            logger.warning('No se proporcionó ID de documento')
            return jsonify({
                'success': False, 
                'error': 'ID de documento no proporcionado'
            }), 400
        
        # Obtener cliente de Elasticsearch
        logger.info('Obteniendo cliente de Elasticsearch...')
        es = get_elasticsearch_client()
        if not es:
            logger.error('No se pudo conectar a Elasticsearch')
            return jsonify({
                'success': False, 
                'error': 'No se pudo conectar al servidor de búsqueda'
            }), 503
        
        # Obtener nombre del índice
        index_name = get_index_name()
        logger.info(f'Intentando eliminar documento {doc_id} del índice {index_name}...')
        
        # Intentar eliminar el documento
        try:
            response = es.delete(
                index=index_name,
                id=doc_id,
                refresh=True  # Forzar actualización del índice
            )
            logger.info(f'Respuesta de Elasticsearch: {response}')
            
            if response.get('result') == 'deleted':
                logger.info(f'Documento {doc_id} eliminado exitosamente')
                return jsonify({
                    'success': True,
                    'message': 'Documento eliminado correctamente'
                })
            else:
                error_msg = f'El documento {doc_id} no pudo ser eliminado. Respuesta: {response}'
                logger.warning(error_msg)
                return jsonify({
                    'success': False,
                    'error': 'No se pudo eliminar el documento',
                    'details': str(response)
                }), 400
                
        except Exception as es_error:
            error_msg = f'Error de Elasticsearch al eliminar documento {doc_id}: {str(es_error)}'
            logger.error(error_msg, exc_info=True)
            return jsonify({
                'success': False,
                'error': 'Error al procesar la solicitud',
                'details': str(es_error)
            }), 500
            
    except Exception as e:
        error_msg = f'Error inesperado al eliminar documento: {str(e)}'
        logger.error(error_msg, exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Error inesperado al procesar la solicitud',
            'details': str(e)
        }), 500
