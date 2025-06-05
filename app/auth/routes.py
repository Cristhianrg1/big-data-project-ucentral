from flask import render_template, request, redirect, url_for, session, flash, jsonify, current_app
from app.extensions import get_mongo_client
from . import auth_bp

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Si el usuario ya está autenticado, redirigir al dashboard
    if 'usuario' in session:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        client = get_mongo_client()
        if not client:
            return render_template('login.html', 
                              error_message='Error de conexión con la base de datos. Por favor, intente más tarde.',
                              version=current_app.config['VERSION_APP'],
                              creador=current_app.config['CREATOR_APP'])
        
        try:
            db = client['administracion']
            security_collection = db['seguridad']
            usuario = request.form['usuario']
            password = request.form['password']
            
            user = security_collection.find_one({
                'usuario': usuario,
                'password': password
            })
            
            if user:
                session['usuario'] = usuario
                next_page = request.args.get('next') or request.form.get('next')
                if next_page and next_page != url_for('auth.login'):
                    return redirect(next_page)
                return redirect(url_for('dashboard'))
            else:
                return render_template('login.html', 
                                    error_message='Usuario o contraseña incorrectos',
                                    version=current_app.config['VERSION_APP'],
                                    creador=current_app.config['CREATOR_APP'],
                                    next=request.args.get('next', ''))
        except Exception as e:
            return render_template('login.html', 
                               error_message=f'Error al validar credenciales: {str(e)}',
                               version=current_app.config['VERSION_APP'],
                               creador=current_app.config['CREATOR_APP'])
        finally:
            client.close()
    
    return render_template('login.html', 
                         version=current_app.config['VERSION_APP'],
                         creador=current_app.config['CREATOR_APP'])

@auth_bp.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect(url_for('auth.login'))

@auth_bp.route('/listar-usuarios')
def listar_usuarios():
    try:
        client = get_mongo_client()
        if not client:
            return jsonify({'error': 'Error de conexión con la base de datos'}), 500
        
        db = client['administracion']
        security_collection = db['seguridad']
        
        usuarios = list(security_collection.find())
        
        for usuario in usuarios:
            usuario['_id'] = str(usuario['_id'])
        
        return jsonify(usuarios)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'client' in locals():
            client.close()
