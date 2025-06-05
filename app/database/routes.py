from flask import render_template, request, redirect, url_for, jsonify, session, flash, current_app, send_file
import json
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import datetime as dt
from . import db_bp
from . import services
from functools import wraps
from bson import ObjectId
from bson.errors import InvalidId

def login_required(f):
    """Decorador para verificar que el usuario haya iniciado sesión"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario' not in session:
            flash('Por favor inicie sesión para acceder a esta página', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@db_bp.route('/mongodb-manager')
@db_bp.route('/mongodb-manager/<path:database>')
@login_required
def gestion_proyecto(database=None):
    """Página principal de gestión de bases de datos"""
    try:
        current_app.logger.info(f'Accediendo a gestion_proyecto con database={database}, args={request.args}')
        
        databases = services.get_databases()
        # Priorizar el parámetro de consulta sobre el de la ruta
        selected_db = request.args.get('database', database or '')
        
        current_app.logger.info(f'Bases de datos disponibles: {databases}')
        current_app.logger.info(f'Base de datos seleccionada: {selected_db}')
        
        # Si es una solicitud AJAX, devolver solo los datos de las colecciones
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            current_app.logger.info('Solicitud AJAX detectada')
            
            if not selected_db:
                current_app.logger.warning('No se seleccionó ninguna base de datos')
                return jsonify({'success': False, 'error': 'No se ha seleccionado ninguna base de datos'}), 400
                
            current_app.logger.info(f'Obteniendo colecciones para la base de datos: {selected_db}')
            collections_data = services.get_collections(selected_db)
            current_app.logger.info(f'Colecciones encontradas: {collections_data}')
            
            response_data = {
                'success': True,
                'collections': collections_data,
                'database': selected_db
            }
            current_app.logger.info(f'Enviando respuesta: {response_data}')
            return jsonify(response_data)
        
        # Para solicitudes normales, renderizar la plantilla completa
        collections_data = []
        if selected_db:
            collections_data = services.get_collections(selected_db)
        
        return render_template('gestion/index.html',
                             databases=databases,
                             selected_db=selected_db,
                             collections_data=collections_data)
    except Exception as e:
        current_app.logger.error(f"Error en gestión_proyecto: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': str(e)}), 500
        flash("Error al cargar la página de gestión", "error")
        return redirect(url_for('database.gestion_proyecto'))

@db_bp.route('/coleccion/<database>/<collection>')
@login_required
def ver_coleccion(database, collection):
    """Ver documentos de una colección"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 10  # Número de documentos por página
        
        # Obtener documentos con paginación
        documents, total = services.get_documents(database, collection, page, per_page)
        
        # Calcular número total de páginas
        pages = (total + per_page - 1) // per_page if total > 0 else 1
        
        return render_template('gestion/ver_coleccion.html',
                             database=database,
                             collection=collection,
                             documents=documents,
                             page=page,
                             pages=pages,
                             total=total)
    except Exception as e:
        current_app.logger.error(f"Error al ver colección {collection}: {str(e)}")
        flash(f"Error al cargar la colección: {str(e)}", "error")
        return redirect(url_for('database.gestion_proyecto'))

@db_bp.route('/api/coleccion/<database>/<collection>')
@login_required
def api_coleccion(database, collection):
    """API para obtener documentos de una colección en formato JSON"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        documents, total = services.get_documents(database, collection, page, per_page)
        
        return jsonify({
            'data': documents,
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page if total > 0 else 1
        })
    except Exception as e:
        current_app.logger.error(f"Error en API colección: {str(e)}")
        return jsonify({'error': str(e)}), 500

@db_bp.route('/crear-db', methods=['GET', 'POST'])
@login_required
def crear_base_datos():
    """Crear una nueva base de datos"""
    if request.method == 'POST':
        db_name = request.form.get('nombre_db', '').strip()
        if not db_name:
            flash('El nombre de la base de datos es requerido', 'error')
            return redirect(url_for('database.crear_base_datos'))
        
        # Validar nombre de la base de datos
        if not db_name.isidentifier() or not db_name.islower():
            flash('El nombre de la base de datos debe contener solo letras minúsculas, números y guiones bajos', 'error')
            return redirect(url_for('database.crear_base_datos'))
        
        success, message = services.create_database(db_name)
        if success:
            flash(message, 'success')
            return redirect(url_for('database.gestion_proyecto', database=db_name))
        else:
            flash(message, 'error')
            return redirect(url_for('database.crear_base_datos'))
    
    return render_template('gestion/crear_db.html')

@db_bp.route('/<database>/crear-coleccion', methods=['GET', 'POST'])
@login_required
def crear_coleccion(database):
    """Crear una nueva colección en una base de datos"""
    current_app.logger.info(f'Iniciando creación de colección en base de datos: {database}')
    
    if request.method == 'POST':
        try:
            current_app.logger.info('Procesando solicitud POST para crear colección')
            collection_name = request.form.get('collection_name', '').strip()
            zip_file = request.files.get('zip_file')
            
            current_app.logger.info(f'Datos recibidos - colección: {collection_name}, archivo: {zip_file.filename if zip_file else "Ninguno"}')
            
            # Validar campos requeridos
            if not collection_name or not zip_file:
                error_msg = 'Todos los campos son requeridos'
                current_app.logger.warning(error_msg)
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'error': error_msg}), 400
                flash(error_msg, 'error')
                return redirect(url_for('database.crear_coleccion', database=database))
            
            # Validar nombre de la colección
            if not collection_name.isidentifier() or not collection_name.islower():
                error_msg = 'El nombre de la colección debe contener solo letras minúsculas, números y guiones bajos'
                current_app.logger.warning(f'Nombre de colección inválido: {collection_name}')
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'error': error_msg}), 400
                flash(error_msg, 'error')
                return redirect(url_for('database.crear_coleccion', database=database))
            
            # Validar extensión del archivo
            if not zip_file.filename.lower().endswith('.zip'):
                error_msg = 'El archivo debe ser un archivo ZIP (.zip)'
                current_app.logger.warning(f'Extensión de archivo no válida: {zip_file.filename}')
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'error': error_msg}), 400
                flash(error_msg, 'error')
                return redirect(url_for('database.crear_coleccion', database=database))
        
            # Crear un directorio temporal para extraer el archivo ZIP
            import tempfile
            import zipfile
            import os
            import json
            
            with tempfile.TemporaryDirectory() as temp_dir:
                current_app.logger.info(f'Directorio temporal creado: {temp_dir}')
                
                # Guardar el archivo ZIP temporalmente
                zip_path = os.path.join(temp_dir, 'uploaded.zip')
                current_app.logger.info(f'Guardando archivo ZIP en: {zip_path}')
                zip_file.save(zip_path)
                
                # Extraer el archivo ZIP
                current_app.logger.info('Extrayendo archivo ZIP...')
                try:
                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        zip_ref.extractall(temp_dir)
                    current_app.logger.info('Archivo ZIP extraído exitosamente')
                except zipfile.BadZipFile as e:
                    error_msg = 'El archivo ZIP está dañado o no es válido'
                    current_app.logger.error(f'Error al extraer ZIP: {str(e)}')
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return jsonify({'error': error_msg}), 400
                    flash(error_msg, 'error')
                    return redirect(url_for('database.crear_coleccion', database=database))
                
                # Procesar archivos JSON
                documents = []
                json_files = []
                
                # Encontrar todos los archivos JSON, ignorando archivos ocultos y de metadatos de macOS
                for root, _, files in os.walk(temp_dir):
                    # Saltar directorios de metadatos de macOS
                    if '__MACOSX' in root or any(part.startswith('.') for part in root.split(os.sep)):
                        current_app.logger.info(f'Ignorando directorio de metadatos: {root}')
                        continue
                        
                    for file in files:
                        # Ignorar archivos ocultos y de metadatos de macOS
                        if file.startswith('._') or file.startswith('.'):
                            current_app.logger.info(f'Ignorando archivo oculto: {file}')
                            continue
                            
                        if file.lower().endswith('.json'):
                            file_path = os.path.join(root, file)
                            json_files.append(file_path)
                            current_app.logger.info(f'Archivo JSON encontrado: {file_path}')
                
                current_app.logger.info(f'Archivos JSON encontrados: {len(json_files)}')
                
                def try_load_json(file_path):
                    # Lista de codificaciones a intentar (en orden de preferencia)
                    encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
                    
                    for encoding in encodings:
                        try:
                            with open(file_path, 'r', encoding=encoding) as f:
                                content = f.read()
                                # Eliminar BOM si está presente
                                if content.startswith('\ufeff'):
                                    content = content[1:]
                                return json.loads(content)
                        except UnicodeDecodeError:
                            continue
                        except json.JSONDecodeError as e:
                            # Si el JSON no es válido en esta codificación, continuamos con la siguiente
                            current_app.logger.warning(f'Error de decodificación JSON con codificación {encoding} en {file_path}: {str(e)}')
                            continue
                    
                    # Si ninguna codificación funcionó, levantar el último error
                    raise json.JSONDecodeError(f'No se pudo decodificar el archivo con ninguna de las codificaciones: {encodings}', doc='', pos=0)
                
                for json_file in json_files:
                    try:
                        current_app.logger.info(f'Procesando archivo: {json_file}')
                        data = try_load_json(json_file)
                        
                        if isinstance(data, list):
                            documents.extend(data)
                            current_app.logger.info(f'Se agregaron {len(data)} documentos de lista')
                        else:
                            documents.append(data)
                            current_app.logger.info('Se agregó 1 documento')
                    except json.JSONDecodeError as e:
                        error_msg = f'Error al procesar el archivo {os.path.basename(json_file)}: Formato JSON inválido'
                        current_app.logger.error(f'Error de JSON: {str(e)} en archivo {json_file}')
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return jsonify({'error': error_msg}), 400
                        flash(error_msg, 'error')
                        return redirect(url_for('database.crear_coleccion', database=database))
                    except Exception as e:
                        error_msg = f'Error al procesar el archivo {os.path.basename(json_file)}: {str(e)}'
                        current_app.logger.error(f'Error inesperado al procesar {json_file}: {str(e)}', exc_info=True)
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return jsonify({'error': error_msg}), 500
                        flash(error_msg, 'error')
                        return redirect(url_for('database.crear_coleccion', database=database))
                
                current_app.logger.info(f'Total de documentos a insertar: {len(documents)}')
                
                if not documents:
                    error_msg = 'No se encontraron documentos JSON válidos en el archivo ZIP'
                    current_app.logger.warning(error_msg)
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return jsonify({'error': error_msg}), 400
                    flash(error_msg, 'error')
                    return redirect(url_for('database.crear_coleccion', database=database))
                
                # Insertar documentos en la colección
                current_app.logger.info(f'Creando colección {collection_name} en base de datos {database}...')
                success, message = services.create_collection(database, collection_name)
                if not success:
                    current_app.logger.error(f'Error al crear colección: {message}')
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return jsonify({'error': message}), 400
                    flash(message, 'error')
                    return redirect(url_for('database.crear_coleccion', database=database))
                
                # Insertar los documentos en lotes
                current_app.logger.info(f'Insertando {len(documents)} documentos en la colección...')
                batch_size = 100  # Tamaño del lote
                success, result = services.insert_many_documents(
                    database, 
                    collection_name, 
                    documents,
                    batch_size=batch_size
                )
                
                if not success and 'Se insertaron 0 de' in result:
                    # Error fatal - no se insertó ningún documento
                    current_app.logger.error(f'Error al insertar documentos: {result}')
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return jsonify({'error': f'Error al importar documentos: {result}'}), 500
                    flash(f'Error al importar documentos: {result}', 'error')
                    return redirect(url_for('database.crear_coleccion', database=database))
                
                # Éxito (parcial o total)
                success_msg = f'Colección "{collection_name}" procesada. {result}'
                current_app.logger.info(success_msg)
                
                # Preparar respuesta
                response_data = {
                    'success': True,
                    'message': success_msg,
                    'redirect': url_for('database.gestion_proyecto', database=database, _external=True)
                }
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify(response_data)
                
                flash(success_msg, 'success' if success else 'warning')
                return redirect(url_for('database.gestion_proyecto', database=database))
                
        except Exception as e:
            error_msg = f'Error inesperado al procesar la solicitud: {str(e)}'
            current_app.logger.error(f'Error inesperado: {str(e)}', exc_info=True)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': error_msg}), 500
            flash(error_msg, 'error')
            return redirect(url_for('database.crear_coleccion', database=database))
    
    # GET request - Mostrar formulario
    current_app.logger.info('Mostrando formulario de creación de colección')
    return render_template('gestion/crear_coleccion.html', database=database)

@db_bp.route('/document/<database>/<collection>/<document_id>', methods=['DELETE'])
@login_required
def eliminar_documento(database, collection, document_id):
    """Eliminar un documento de una colección"""
    try:
        # Validar el ID del documento
        try:
            doc_id = ObjectId(document_id)
        except (InvalidId, TypeError):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': 'ID de documento no válido'}), 400
            flash('ID de documento no válido', 'error')
            return redirect(url_for('database.ver_coleccion', database=database, collection=collection))
        
        # Verificar si la colección existe
        if not services.collection_exists(database, collection):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': 'La colección no existe'}), 404
            flash('La colección no existe', 'error')
            return redirect(url_for('database.gestion_proyecto'))
        
        # Eliminar el documento
        success, message = services.delete_document(database, collection, document_id)
        
        if not success:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': message}), 404
            flash(message, 'error')
            return redirect(url_for('database.ver_coleccion', database=database, collection=collection))
        
        # Log de la acción
        current_app.logger.info(f"Documento eliminado: {database}.{collection}.{document_id} por el usuario {session.get('usuario', 'desconocido')}")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True, 
                'message': message,
                'deleted_id': document_id
            })
            
        flash(message, 'success')
        return redirect(url_for('database.ver_coleccion', database=database, collection=collection))
        
    except Exception as e:
        error_msg = f"Error al eliminar documento: {str(e)}"
        current_app.logger.error(error_msg, exc_info=True)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': str(e)}), 500
            
        flash(f'Error al eliminar el documento: {str(e)}', 'error')
        return redirect(url_for('database.ver_coleccion', database=database, collection=collection))

@db_bp.route('/<database>/eliminar', methods=['POST'])
@login_required
def eliminar_base_datos(database):
    """Eliminar una base de datos"""
    try:
        client = services.get_mongo_client()
        if not client:
            flash('Error al conectar con MongoDB', 'error')
            return redirect(url_for('database.gestion_proyecto'))
        
        # Verificar si la base de datos existe
        if database not in client.list_database_names():
            flash(f'La base de datos "{database}" no existe', 'error')
            return redirect(url_for('database.gestion_proyecto'))
        
        # Eliminar la base de datos
        client.drop_database(database)
        flash(f'Base de datos "{database}" eliminada exitosamente', 'success')
        return redirect(url_for('database.gestion_proyecto'))
        
    except Exception as e:
        error_msg = f'Error al eliminar la base de datos: {str(e)}'
        current_app.logger.error(error_msg)
        flash(error_msg, 'error')
        return redirect(url_for('database.gestion_proyecto'))
    finally:
        if 'client' in locals():
            client.close()

@db_bp.route('/document/<database>/<collection>/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_documento(database, collection):
    """Crear un nuevo documento en la colección"""
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            doc_data = request.form.get('documento')
            try:
                doc = json.loads(doc_data)
            except json.JSONDecodeError as e:
                flash('Error en el formato JSON: ' + str(e), 'error')
                return render_template('gestion/editar_documento.html', 
                                   database=database, 
                                   collection=collection,
                                   documento=doc_data)
            
            # Insertar el documento
            success, result = services.insert_document(database, collection, doc)
            
            if success:
                flash('Documento creado exitosamente', 'success')
                return redirect(url_for('database.ver_coleccion', database=database, collection=collection))
            else:
                flash(f'Error al crear el documento: {result}', 'error')
                
        except Exception as e:
            current_app.logger.error(f"Error al crear documento: {str(e)}")
            flash(f'Error al crear el documento: {str(e)}', 'error')
    
    # Mostrar formulario con documento vacío
    return render_template('gestion/editar_documento.html',
                         database=database,
                         collection=collection,
                         documento={
    "_id": {
        "$oid": ""
    },
    "createdAt": {
        "$date": ""
    },
    "updatedAt": {
        "$date": ""
    }
})

@db_bp.route('/document/<database>/<collection>/<document_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_documento(database, collection, document_id):
    """Editar un documento existente"""
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            doc_data = request.form.get('documento')
            try:
                doc = json.loads(doc_data)
            except json.JSONDecodeError as e:
                flash('Error en el formato JSON: ' + str(e), 'error')
                return render_template('gestion/editar_documento.html', 
                                   database=database, 
                                   collection=collection,
                                   documento=doc_data,
                                   document_id=document_id)
            
            # Actualizar el documento
            success, result = services.update_document(database, collection, document_id, doc)
            
            if success:
                flash('Documento actualizado exitosamente', 'success')
                return redirect(url_for('database.ver_coleccion', database=database, collection=collection))
            else:
                flash(f'Error al actualizar el documento: {result}', 'error')
                
        except Exception as e:
            current_app.logger.error(f"Error al actualizar documento: {str(e)}")
            flash(f'Error al actualizar el documento: {str(e)}', 'error')
    
    # Obtener el documento actual
    doc = services.get_document(database, collection, document_id)
    if not doc:
        flash('Documento no encontrado', 'error')
        return redirect(url_for('database.ver_coleccion', database=database, collection=collection))
    
    return render_template('gestion/editar_documento.html',
                         database=database,
                         collection=collection,
                         documento=json.dumps(doc, indent=2, default=str),
                         document_id=document_id)

@db_bp.route('/document/<database>/<collection>/importar', methods=['GET', 'POST'])
@login_required
def importar_documentos(database, collection):
    """Importar documentos desde un archivo JSON"""
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No se seleccionó ningún archivo', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No se seleccionó ningún archivo', 'error')
            return redirect(request.url)
        
        if file and file.filename.endswith('.json'):
            try:
                # Leer el archivo JSON
                data = json.load(file)
                
                # Si es un array, insertar múltiples documentos
                if isinstance(data, list):
                    success, result = services.insert_many_documents(database, collection, data)
                    if success:
                        flash(f'Se importaron {len(result.inserted_ids)} documentos exitosamente', 'success')
                    else:
                        flash(f'Error al importar documentos: {result}', 'error')
                # Si es un objeto, insertar un solo documento
                elif isinstance(data, dict):
                    success, result = services.insert_document(database, collection, data)
                    if success:
                        flash('Documento importado exitosamente', 'success')
                    else:
                        flash(f'Error al importar documento: {result}', 'error')
                else:
                    flash('Formato de archivo no válido', 'error')
                
                return redirect(url_for('database.ver_coleccion', database=database, collection=collection))
                
            except json.JSONDecodeError:
                flash('El archivo no es un JSON válido', 'error')
            except Exception as e:
                current_app.logger.error(f"Error al importar documentos: {str(e)}")
                flash(f'Error al importar documentos: {str(e)}', 'error')
        else:
            flash('Formato de archivo no soportado. Solo se aceptan archivos .json', 'error')
    
    return render_template('gestion/importar_documentos.html',
                         database=database,
                         collection=collection)

@db_bp.route('/<database>/eliminar-coleccion/<collection>', methods=['POST'])
@login_required
def eliminar_coleccion(database, collection):
    """Eliminar una colección"""
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    try:
        client = services.get_mongo_client()
        if not client:
            error_msg = 'Error al conectar con MongoDB'
            if is_ajax:
                return jsonify({'success': False, 'error': error_msg}), 500
            flash(error_msg, 'error')
            return redirect(url_for('database.gestion_proyecto', database=database))
        
        # Verificar si la base de datos existe
        if database not in client.list_database_names():
            error_msg = f'La base de datos "{database}" no existe'
            if is_ajax:
                return jsonify({'success': False, 'error': error_msg}), 404
            flash(error_msg, 'error')
            return redirect(url_for('database.gestion_proyecto'))
        
        db = client[database]
        
        # Verificar si la colección existe
        if collection not in db.list_collection_names():
            error_msg = f'La colección "{collection}" no existe'
            if is_ajax:
                return jsonify({'success': False, 'error': error_msg}), 404
            flash(error_msg, 'error')
            return redirect(url_for('database.gestion_proyecto', database=database))
        
        # Eliminar la colección
        db.drop_collection(collection)
        success_msg = f'Colección "{collection}" eliminada exitosamente'
        
        if is_ajax:
            return jsonify({
                'success': True,
                'message': success_msg,
                'redirect': url_for('database.gestion_proyecto', database=database)
            })
            
        flash(success_msg, 'success')
        return redirect(url_for('database.gestion_proyecto', database=database))
        
    except Exception as e:
        error_msg = f'Error al eliminar la colección: {str(e)}'
        current_app.logger.error(error_msg)
        
        if is_ajax:
            return jsonify({'success': False, 'error': error_msg}), 500
            
        flash(error_msg, 'error')
        return redirect(url_for('database.gestion_proyecto', database=database))
    finally:
        if 'client' in locals():
            client.close()
