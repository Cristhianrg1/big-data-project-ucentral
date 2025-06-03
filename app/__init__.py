import os
from flask import Flask, jsonify, redirect, url_for, session, render_template
from . import config

def create_app():
    """Crea y configura la aplicación Flask"""
    # Configurar rutas de plantillas
    template_dir = os.path.abspath('app/templates')
    static_dir = os.path.abspath('app/static')
    
    app = Flask(__name__, 
              template_folder=template_dir,
              static_folder=static_dir)
    
    # Cargar configuración
    app.config.from_object(config.Config)
    
    # Configuración para desarrollo
    if app.config['DEBUG']:
        app.config['TEMPLATES_AUTO_RELOAD'] = True
        app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
    
    # Configuración de la sesión
    app.config['SESSION_COOKIE_SECURE'] = not app.config['DEBUG']
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    
    # Registrar blueprints
    from .auth import auth_bp
    from .database import db_bp
    from .main import main_bp
    from .elasticsearch import elastic_bp
    
    # Registrar blueprints con sus prefijos de URL
    app.register_blueprint(main_bp, url_prefix='')
    app.register_blueprint(auth_bp, url_prefix='')
    app.register_blueprint(db_bp, url_prefix='')
    
    # Registrar el blueprint de Elasticsearch con el prefijo /gestion/elastic
    app.register_blueprint(elastic_bp, url_prefix='/gestion/elastic')
        
    # Ruta de dashboard - Requiere autenticación
    @app.route('/dashboard')
    def dashboard():
        if 'usuario' not in session:
            return redirect(url_for('auth.login', next=url_for('dashboard')))
        return render_template('gestion/dashboard.html')
    
    @app.route('/health')
    def health_check():
        return jsonify({
            'status': 'healthy',
            'version': app.config['VERSION_APP']
        }), 200
    
    # Inyectar variables globales a las plantillas
    @app.context_processor
    def inject_config():
        return {
            'version': app.config['VERSION_APP'],
            'creador': app.config['CREATOR_APP']
        }
    
    return app
