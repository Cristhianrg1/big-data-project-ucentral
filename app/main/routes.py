from flask import render_template, current_app, request, flash, redirect, url_for
from app.extensions import get_mongo_client
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

@main_bp.route('/buscador')
def buscador():
    return render_template('buscador.html',
                         creador=current_app.config.get('CREADOR', 'XYZ'),
                         version=current_app.config.get('VERSION_APP', '1.0.0'))
