from flask import render_template, current_app, request, flash, redirect, url_for, jsonify, session
from app.extensions import get_mongo_client, requires_elasticsearch
from bson import ObjectId
from datetime import datetime
from . import main_bp

@main_bp.route('/')
def index():
    return render_template('index.html', 
                         creador=current_app.config.get('CREADOR', 'XYZ'),
                         version=current_app.config.get('VERSION_APP', '1.0.0'))

@main_bp.route('/about')
def about():
    return render_template('about.html',
                         creador=current_app.config.get('CREADOR', 'XYZ'),
                         version=current_app.config.get('VERSION_APP', '1.0.0'))

@main_bp.route('/contacto', methods=['GET', 'POST'])
def contacto():
    if request.method == 'POST':
        # Validar que todos los campos requeridos estén presentes
        required_fields = ['nombre', 'email', 'asunto', 'mensaje']
        missing_fields = [field for field in required_fields if not request.form.get(field)]
        
        if missing_fields:
            flash('Por favor complete todos los campos obligatorios.', 'error')
        else:
            try:
                # Obtener los datos del formulario
                contacto_data = {
                    'nombre': request.form.get('nombre'),
                    'email': request.form.get('email'),
                    'asunto': request.form.get('asunto'),
                    'mensaje': request.form.get('mensaje'),
                    'fecha_creacion': datetime.utcnow(),
                    'estado': 'nuevo'  # Puedes usar estados como 'nuevo', 'en_proceso', 'atendido', etc.
                }
                
                # Obtener conexión a MongoDB
                client = get_mongo_client()
                if not client:
                    flash('Error al conectar con la base de datos. Por favor, intente más tarde.', 'error')
                    return redirect(url_for('main.contacto'))
                
                # Seleccionar la base de datos y la colección
                db = client['administracion']  # O el nombre de tu base de datos
                coleccion = db['contacto_clientes']
                
                # Insertar el documento
                resultado = coleccion.insert_one(contacto_data)
                
                if resultado.inserted_id:
                    flash('¡Gracias por tu mensaje! Nos pondremos en contacto contigo pronto.', 'success')
                else:
                    flash('Hubo un error al enviar tu mensaje. Por favor, inténtalo de nuevo.', 'error')
                
                # Cerrar la conexión
                client.close()
                
                return redirect(url_for('main.contacto'))
                
            except Exception as e:
                current_app.logger.error(f'Error al guardar el mensaje de contacto: {str(e)}')
                flash('Ocurrió un error al procesar tu solicitud. Por favor, inténtalo de nuevo más tarde.', 'error')
    
    return render_template('contacto.html',
                         creador=current_app.config.get('CREADOR', 'XYZ'),
                         version=current_app.config.get('VERSION_APP', '1.0.0'))

@main_bp.route('/buscador', methods=['GET', 'POST'])
@requires_elasticsearch
def buscador(es_client=None):
    """
    Ruta del buscador que requiere Elasticsearch.
    El parámetro es_client es proporcionado automáticamente por el decorador @requires_elasticsearch
    """
    try:
        resultados = None
        
        # Obtener parámetros de la solicitud actual (GET o POST)
        query = request.form.get('query', request.args.get('query', '')).strip()
        fecha_desde = request.form.get('fecha_desde', request.args.get('fecha_desde', ''))
        fecha_hasta = request.form.get('fecha_hasta', request.args.get('fecha_hasta', ''))
        
        # Verificar si hay una búsqueda guardada en la sesión
        last_search = session.get('last_search', {})
        
        # Si es GET sin parámetros pero hay una búsqueda previa, usarla
        if request.method == 'GET' and not query and last_search:
            query = last_search.get('query', '')
            fecha_desde = last_search.get('fecha_desde', '')
            fecha_hasta = last_search.get('fecha_hasta', '')
            
            # Si hay parámetros de búsqueda, redirigir con los parámetros en la URL
            if query or fecha_desde or fecha_hasta:
                return redirect(url_for('main.buscador', 
                                     query=query, 
                                     fecha_desde=fecha_desde, 
                                     fecha_hasta=fecha_hasta))
        
        # Realizar búsqueda si hay parámetros (ya sea POST o GET con parámetros)
        if (request.method == 'POST' or (request.method == 'GET' and (query or fecha_desde or fecha_hasta))):
            # Construir la consulta base
            must_conditions = []
            
            # Añadir búsqueda de texto si existe
            if query:
                must_conditions.append({
                    "multi_match": {
                        "query": query,
                        "fields": ["titulo^2", "contenido", "autor"],
                        "fuzziness": "AUTO"
                    }
                })
            
            # Añadir filtro de fechas si existe
            range_condition = {}
            if fecha_desde:
                range_condition["gte"] = fecha_desde
            if fecha_hasta:
                range_condition["lte"] = fecha_hasta
                
            if range_condition:
                must_conditions.append({
                    "range": {
                        "fecha_publicacion": range_condition
                    }
                })
            
            # Construir la consulta final
            query_body = {
                "query": {
                    "bool": {
                        "must": must_conditions
                    }
                },
                "highlight": {
                    "fields": {
                        "contenido": {}
                    }
                },
                "sort": [
                    { "fecha_publicacion": "desc" }  # Ordenar por fecha más reciente primero
                ]
            }
            
            # Realizar búsqueda en Elasticsearch
            resultados = es_client.search(
                index=current_app.config['ELASTICSEARCH_INDEX'],
                body=query_body
            )
        
        # Guardar parámetros de búsqueda en la sesión solo si hay búsqueda
        if query or fecha_desde or fecha_hasta:
            session['last_search'] = {
                'query': query,
                'fecha_desde': fecha_desde,
                'fecha_hasta': fecha_hasta
            }
        elif 'last_search' in session:
            # Si no hay parámetros de búsqueda, limpiar la búsqueda guardada
            session.pop('last_search', None)
        
        return render_template('buscador.html',
                           creador=current_app.config.get('CREADOR', 'XYZ'),
                           version=current_app.config.get('VERSION_APP', '1.0.0'),
                           elasticsearch_available=True,
                           resultados=resultados,
                           query=query,
                           fecha_desde=fecha_desde,
                           fecha_hasta=fecha_hasta)
    except Exception as e:
        current_app.logger.error(f'Error en la búsqueda: {str(e)}')
        flash('Ocurrió un error al realizar la búsqueda. Por favor, intente más tarde.', 'error')
        return render_template('buscador.html',
                           creador=current_app.config.get('CREADOR', 'XYZ'),
                           version=current_app.config.get('VERSION_APP', '1.0.0'),
                           elasticsearch_available=False,
                           resultados=None,
                           query="",
                           fecha_desde="",
                           fecha_hasta="")

@main_bp.route('/documento/<document_id>')
@requires_elasticsearch
def ver_documento(document_id, es_client=None):
    """
    Muestra un documento completo por su ID
    """
    try:
        # Obtener el documento de Elasticsearch
        resultado = es_client.get(
            index=current_app.config['ELASTICSEARCH_INDEX'],
            id=document_id
        )
        
        # Obtener la última búsqueda de la sesión
        last_search = session.get('last_search', {})
        
        return render_template('ver_documento.html',
                           creador=current_app.config.get('CREADOR', 'XYZ'),
                           version=current_app.config.get('VERSION_APP', '1.0.0'),
                           documento=resultado['_source'],
                           doc_id=document_id,
                           last_search=last_search)
    except Exception as e:
        current_app.logger.error(f'Error al obtener el documento: {str(e)}')
        flash('No se pudo cargar el documento solicitado.', 'error')
        return redirect(url_for('main.buscador'))
