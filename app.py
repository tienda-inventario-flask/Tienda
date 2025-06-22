import os
import math
import io
import csv
import json
import uuid
import psycopg2
from psycopg2.extras import DictCursor
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response, jsonify
from functools import wraps
from dotenv import load_dotenv

# Carga las variables de entorno del archivo .env (para desarrollo local)
load_dotenv()

app = Flask(__name__)
# La clave secreta ahora se lee de una variable de entorno para mayor seguridad en producción
app.secret_key = os.environ.get('SECRET_KEY', 'ricardo123')
PER_PAGE = 10

# --- FUNCIÓN DE CONEXIÓN A POSTGRESQL ---
def get_db_connection():
    try:
        conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
        return conn
    except Exception as e:
        print(f"Error de conexión a la base de datos: {e}")
        return None

# --- FUNCIÓN PARA REGISTRAR ACTIVIDAD ---
def registrar_actividad(accion, descripcion=""):
    if 'user_id' not in session: return
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    'INSERT INTO historial_actividad (empresa_id, usuario_id, usuario_username, accion, descripcion) VALUES (%s, %s, %s, %s, %s)',
                    (session.get('empresa_id', 0), session['user_id'], session['username'], accion, descripcion)
                )
            conn.commit()
        except Exception as e:
            print(f"Error al registrar actividad: {e}")
        finally:
            conn.close()

# --- DECORADORES DE SEGURIDAD ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Debes iniciar sesión para ver esta página.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('rol') not in ['admin', 'superadmin']:
            flash('No tienes permiso para realizar esta acción.', 'danger')
            return redirect(url_for('mostrar_inventario'))
        return f(*args, **kwargs)
    return decorated_function

def superadmin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('rol') != 'superadmin':
            flash('Acceso denegado. Esta área es solo para el super-administrador.', 'danger')
            return redirect(url_for('mostrar_inventario'))
        return f(*args, **kwargs)
    return decorated_function

# --- RUTAS DE AUTENTICACIÓN ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('superadmin_dashboard') if session.get('rol') == 'superadmin' else url_for('mostrar_inventario'))
    if request.method == 'POST':
        username, password = request.form['username'], request.form['password']
        conn = get_db_connection()
        if not conn:
            flash('Error de conexión con la base de datos.', 'danger')
            return render_template('login.html')
        try:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute('SELECT * FROM usuarios WHERE username = %s', (username,))
                user = cur.fetchone()
                if user and check_password_hash(user['password'], password):
                    cur.execute('SELECT nombre_empresa FROM empresas WHERE id = %s', (user['empresa_id'],))
                    empresa = cur.fetchone()
                    session.clear()
                    session.update({
                        'user_id': user['id'], 'username': user['username'], 'rol': user['rol'],
                        'empresa_id': user['empresa_id'], 'nombre_empresa': empresa['nombre_empresa']
                    })
                    registrar_actividad('INICIO_SESION')
                    if user['rol'] == 'superadmin':
                        return redirect(url_for('superadmin_dashboard'))
                    return redirect(url_for('mostrar_inventario'))
            flash('Nombre de usuario o contraseña incorrectos.', 'danger')
        except Exception as e:
            print(f"Error de DB en login: {e}")
            flash('Ocurrió un error al intentar iniciar sesión.', 'danger')
        finally:
            if conn: conn.close()
    return render_template('login.html')

@app.route('/registro')
def registro():
    flash('El registro público está desactivado. Contacte al administrador del sistema.', 'info')
    return redirect(url_for('login'))

@app.route('/logout')
@login_required
def logout():
    registrar_actividad('CIERRE_SESION')
    session.clear()
    flash('Has cerrado sesión exitosamente.', 'success')
    return redirect(url_for('login'))


# --- RUTAS DE SUPER-ADMINISTRADOR ---
@app.route('/superadmin')
@login_required
@superadmin_required
def superadmin_dashboard():
    conn = get_db_connection()
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute('SELECT e.*, (SELECT COUNT(u.id) FROM usuarios u WHERE u.empresa_id = e.id) as user_count FROM empresas e WHERE e.id != %s ORDER BY e.nombre_empresa', (session['empresa_id'],))
        empresas = cur.fetchall()
    conn.close()
    return render_template('superadmin_dashboard.html', empresas=empresas)

@app.route('/superadmin/crear_empresa', methods=['GET', 'POST'])
@login_required
@superadmin_required
def crear_empresa():
    if request.method == 'POST':
        nombre_empresa, admin_username, admin_password = request.form['nombre_empresa'], request.form['admin_username'], request.form['admin_password']
        if not all([nombre_empresa, admin_username, admin_password]):
            flash('Todos los campos son obligatorios.', 'danger')
            return render_template('crear_empresa.html')
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute('SELECT id FROM empresas WHERE nombre_empresa = %s', (nombre_empresa,))
                if cur.fetchone():
                    flash('Ya existe una empresa con ese nombre.', 'danger')
                    return render_template('crear_empresa.html')
                cur.execute('SELECT id FROM usuarios WHERE username = %s', (admin_username,))
                if cur.fetchone():
                    flash('Ese nombre de usuario para el admin ya está en uso globalmente.', 'danger')
                    return render_template('crear_empresa.html')
                cur.execute('INSERT INTO empresas (nombre_empresa) VALUES (%s) RETURNING id', (nombre_empresa,))
                empresa_id = cur.fetchone()['id']
                hashed_password = generate_password_hash(admin_password)
                cur.execute('INSERT INTO usuarios (empresa_id, username, password, rol) VALUES (%s, %s, %s, %s)', (empresa_id, admin_username, hashed_password, 'admin'))
            conn.commit()
            registrar_actividad('EMPRESA_CREADA', f"Creó la empresa '{nombre_empresa}' y su admin '{admin_username}'.")
            flash(f'Empresa "{nombre_empresa}" creada con éxito.', 'success')
            return redirect(url_for('superadmin_dashboard'))
        except Exception as e:
            conn.rollback()
            flash(f"Error de base de datos: {e}", "danger")
        finally:
            if conn: conn.close()
    return render_template('crear_empresa.html')

@app.route('/superadmin/eliminar_empresa/<int:empresa_id>', methods=['POST'])
@login_required
@superadmin_required
def eliminar_empresa(empresa_id):
    if empresa_id == session['empresa_id']:
        flash('No puedes eliminar tu propia empresa de sistema.', 'danger')
        return redirect(url_for('superadmin_dashboard'))
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute('SELECT nombre_empresa FROM empresas WHERE id = %s', (empresa_id,))
            empresa = cur.fetchone()
            if empresa:
                cur.execute('DELETE FROM empresas WHERE id = %s', (empresa_id,))
                conn.commit()
                registrar_actividad('EMPRESA_ELIMINADA', f"Eliminó la empresa '{empresa['nombre_empresa']}' (ID: {empresa_id}).")
                flash(f"La empresa '{empresa['nombre_empresa']}' y todos sus datos han sido eliminados.", 'success')
            else:
                flash('La empresa no existe.', 'danger')
    except Exception as e:
        conn.rollback()
        flash(f"Error de base de datos: {e}", "danger")
    finally:
        if conn: conn.close()
    return redirect(url_for('superadmin_dashboard'))

# --- RUTAS DE GESTIÓN DE CUENTA ---
@app.route('/empresa/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_empresa():
    empresa_id = session['empresa_id']
    conn = get_db_connection()
    if request.method == 'POST':
        nombre_empresa, direccion, telefono, rnc = request.form['nombre_empresa'], request.form['direccion'], request.form['telefono'], request.form['rnc']
        if not nombre_empresa: flash('El nombre de la empresa no puede estar vacío.', 'danger')
        else:
            with conn.cursor() as cur:
                cur.execute('UPDATE empresas SET nombre_empresa = %s, direccion = %s, telefono = %s, rnc = %s WHERE id = %s',
                             (nombre_empresa, direccion, telefono, rnc, empresa_id))
            conn.commit()
            session['nombre_empresa'] = nombre_empresa
            registrar_actividad('EMPRESA_EDITADA', 'Se actualizaron los datos del perfil de la empresa.')
            flash('Datos de la empresa actualizados con éxito.', 'success')
        conn.close()
        return redirect(url_for('editar_empresa'))
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute('SELECT * FROM empresas WHERE id = %s', (empresa_id,))
        empresa = cur.fetchone()
    conn.close()
    return render_template('editar_empresa.html', empresa=empresa)

@app.route('/perfil/cambiar_password', methods=['GET', 'POST'])
@login_required
def cambiar_password():
    if request.method == 'POST':
        password_actual, nueva_password, confirmar_password = request.form['password_actual'], request.form['nueva_password'], request.form['confirmar_password']
        if not nueva_password or nueva_password != confirmar_password:
            flash('Las nuevas contraseñas no coinciden o están vacías.', 'danger')
            return redirect(url_for('cambiar_password'))
        conn = get_db_connection()
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute('SELECT password FROM usuarios WHERE id = %s', (session['user_id'],))
            user = cur.fetchone()
            if not check_password_hash(user['password'], password_actual):
                flash('La contraseña actual es incorrecta.', 'danger')
            else:
                hashed_password = generate_password_hash(nueva_password)
                cur.execute('UPDATE usuarios SET password = %s WHERE id = %s', (hashed_password, session['user_id']))
                conn.commit()
                registrar_actividad('PASSWORD_CAMBIADA', f"El usuario '{session['username']}' cambió su contraseña.")
                flash('Contraseña actualizada con éxito.', 'success')
        conn.close()
        return redirect(url_for('cambiar_password'))
    return render_template('cambiar_password.html')

# --- RUTAS PRINCIPALES Y CRUD ---
@app.route('/')
@login_required
def mostrar_inventario():
    if session.get('rol') == 'superadmin':
        return redirect(url_for('superadmin_dashboard'))
    conn = get_db_connection()
    if not conn: return "Error: No se pudo conectar a la base de datos.", 500
    with conn.cursor(cursor_factory=DictCursor) as cur:
        empresa_id, page, query = session['empresa_id'], request.args.get('page', 1, type=int), request.args.get('q')
        offset = (page - 1) * PER_PAGE
        base_where = ' WHERE empresa_id = %s AND activo = TRUE '
        params = [empresa_id]
        if query:
            search_term = f"%{query}%"
            where_clause = base_where + ' AND (nombre ILIKE %s OR marca ILIKE %s)'
            params.extend([search_term, search_term])
        else: where_clause = base_where
        cur.execute('SELECT COUNT(id) AS total FROM productos' + where_clause, params)
        total_productos = cur.fetchone()['total'] or 0
        cur.execute('SELECT SUM(cantidad) AS total FROM productos' + where_clause, params)
        total_stock = cur.fetchone()['total'] or 0
        cur.execute('SELECT SUM(precio * cantidad) AS total FROM productos' + where_clause, params)
        valor_inventario = cur.fetchone()['total'] or 0
        total_pages = math.ceil(total_productos / PER_PAGE)
        main_query = 'SELECT * FROM productos' + where_clause + ' ORDER BY id DESC LIMIT %s OFFSET %s'
        params.extend([PER_PAGE, offset])
        cur.execute(main_query, params)
        productos = cur.fetchall()
    conn.close()
    return render_template('index.html', inventario=productos, query=query, page=page, total_pages=total_pages, total_productos=total_productos, total_stock=total_stock, valor_inventario=valor_inventario, PER_PAGE=PER_PAGE)

def get_producto(producto_id):
    conn = get_db_connection()
    producto = None
    if conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute('SELECT * FROM productos WHERE id = %s AND empresa_id = %s', (producto_id, session['empresa_id']))
            producto = cur.fetchone()
        conn.close()
    return producto

@app.route('/agregar', methods=['GET', 'POST'])
@login_required
@admin_required
def agregar_producto():
    if request.method == 'POST':
        nombre, marca, modelo = request.form['nombre'], request.form['marca'], request.form['modelo']
        precio, cantidad = float(request.form['precio']), int(request.form['cantidad'])
        conn = get_db_connection()
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute('INSERT INTO productos (empresa_id, nombre, marca, modelo, precio, cantidad) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id',
                        (session['empresa_id'], nombre, marca, modelo, precio, cantidad))
            producto_id = cur.fetchone()['id']
        conn.commit()
        conn.close()
        registrar_actividad('PRODUCTO_CREADO', f"Creó el producto '{nombre}' (ID: {producto_id}).")
        flash('¡Producto añadido con éxito!', 'success')
        return redirect(url_for('mostrar_inventario'))
    return render_template('agregar_producto.html')

@app.route('/editar/<int:producto_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_producto(producto_id):
    producto = get_producto(producto_id)
    if producto is None:
        flash('Producto no encontrado o no tienes permiso para editarlo.', 'danger')
        return redirect(url_for('mostrar_inventario'))
    if request.method == 'POST':
        nombre, marca, modelo = request.form['nombre'], request.form['marca'], request.form['modelo']
        precio, cantidad = float(request.form['precio']), int(request.form['cantidad'])
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute('UPDATE productos SET nombre = %s, marca = %s, modelo = %s, precio = %s, cantidad = %s WHERE id = %s AND empresa_id = %s',(nombre, marca, modelo, precio, cantidad, producto_id, session['empresa_id']))
        conn.commit()
        conn.close()
        registrar_actividad('PRODUCTO_EDITADO', f"Editó el producto '{nombre}' (ID: {producto_id}).")
        flash('¡Producto actualizado correctamente!', 'success')
        return redirect(url_for('mostrar_inventario'))
    return render_template('editar_producto.html', producto=producto)

@app.route('/eliminar/<int:producto_id>', methods=['POST'])
@login_required
@admin_required
def eliminar_producto(producto_id):
    producto = get_producto(producto_id)
    if producto:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute('UPDATE productos SET activo = FALSE WHERE id = %s AND empresa_id = %s', (producto_id, session['empresa_id']))
        conn.commit()
        conn.close()
        registrar_actividad('PRODUCTO_DESACTIVADO', f"Archivó el producto '{producto['nombre']}' (ID: {producto_id}).")
        flash('Producto archivado con éxito.', 'warning')
    else: flash('Producto no encontrado.', 'danger')
    return redirect(url_for('mostrar_inventario'))

@app.route('/inventario/archivados')
@login_required
@admin_required
def ver_archivados():
    conn = get_db_connection()
    page = request.args.get('page', 1, type=int)
    offset = (page - 1) * PER_PAGE
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute('SELECT COUNT(id) AS total FROM productos WHERE empresa_id = %s AND activo = FALSE', (session['empresa_id'],))
        total_items = cur.fetchone()['total'] or 0
        total_pages = math.ceil(total_items / PER_PAGE)
        cur.execute('SELECT * FROM productos WHERE empresa_id = %s AND activo = FALSE ORDER BY id DESC LIMIT %s OFFSET %s',
                    (session['empresa_id'], PER_PAGE, offset))
        productos_archivados = cur.fetchall()
    conn.close()
    return render_template('archivados.html', inventario=productos_archivados, page=page, total_pages=total_pages, PER_PAGE=PER_PAGE)

@app.route('/reactivar/<int:producto_id>', methods=['POST'])
@login_required
@admin_required
def reactivar_producto(producto_id):
    producto = get_producto(producto_id)
    if producto:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute('UPDATE productos SET activo = TRUE WHERE id = %s AND empresa_id = %s', (producto_id, session['empresa_id']))
        conn.commit()
        conn.close()
        registrar_actividad('PRODUCTO_REACTIVADO', f"Reactivó el producto '{producto['nombre']}' (ID: {producto_id}).")
        flash('Producto reactivado con éxito.', 'success')
    else: flash('Producto no encontrado.', 'danger')
    return redirect(url_for('ver_archivados'))

@app.route('/reportes')
@login_required
def reportes():
    conn = get_db_connection()
    with conn.cursor(cursor_factory=DictCursor) as cur:
        empresa_id = session['empresa_id']
        cur.execute('SELECT nombre, cantidad FROM productos WHERE empresa_id = %s AND activo = TRUE ORDER BY cantidad DESC LIMIT 5', (empresa_id,))
        top_stock_productos = cur.fetchall()
        cur.execute('SELECT marca, COUNT(id) as total FROM productos WHERE empresa_id = %s AND activo = TRUE GROUP BY marca', (empresa_id,))
        productos_por_marca = cur.fetchall()
    conn.close()
    stock_labels = [row['nombre'] for row in top_stock_productos]
    stock_data = [row['cantidad'] for row in top_stock_productos]
    marca_labels = [row['marca'] for row in productos_por_marca]
    marca_data = [row['total'] for row in productos_por_marca]
    return render_template('reportes.html', stock_labels=json.dumps(stock_labels), stock_data=json.dumps(stock_data), marca_labels=json.dumps(marca_labels), marca_data=json.dumps(marca_data))

@app.route('/exportar_csv')
@login_required
def exportar_csv():
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute('SELECT id, nombre, marca, modelo, precio, cantidad FROM productos WHERE empresa_id = %s AND activo = TRUE ORDER BY id', (session['empresa_id'],))
        productos = cur.fetchall()
    conn.close()
    output, writer = io.StringIO(), csv.writer(output)
    writer.writerow(['ID', 'Nombre', 'Marca', 'Modelo', 'Precio', 'Cantidad en Stock'])
    for producto in productos: writer.writerow(producto)
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=inventario_activo.csv'
    response.headers['Content-type'] = 'text/csv'
    return response

@app.route('/admin/usuarios')
@login_required
@admin_required
def gestionar_usuarios():
    conn = get_db_connection()
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute('SELECT id, username, rol, creado FROM usuarios WHERE empresa_id = %s ORDER BY username', (session['empresa_id'],))
        usuarios = cur.fetchall()
    conn.close()
    return render_template('admin_usuarios.html', usuarios=usuarios)

@app.route('/admin/agregar_usuario', methods=['GET', 'POST'])
@login_required
@admin_required
def agregar_usuario():
    if request.method == 'POST':
        username, password, rol = request.form['username'], request.form['password'], 'empleado'
        empresa_id = session['empresa_id']
        conn = get_db_connection()
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute('SELECT id FROM usuarios WHERE username = %s AND empresa_id = %s', (username, empresa_id))
            if cur.fetchone():
                flash('Ya existe un usuario con ese nombre en tu empresa.', 'danger')
            else:
                hashed_password = generate_password_hash(password)
                cur.execute('INSERT INTO usuarios (empresa_id, username, password, rol) VALUES (%s, %s, %s, %s) RETURNING id',
                            (empresa_id, username, hashed_password, rol))
                nuevo_usuario_id = cur.fetchone()['id']
                conn.commit()
                registrar_actividad('USUARIO_CREADO', f"Creó al usuario '{username}' (ID: {nuevo_usuario_id}) con el rol '{rol}'.")
                flash(f'El empleado "{username}" ha sido creado con éxito.', 'success')
                conn.close()
                return redirect(url_for('gestionar_usuarios'))
        conn.close()
    return render_template('agregar_usuario.html')

@app.route('/admin/cambiar_rol/<int:usuario_id>', methods=['POST'])
@login_required
@admin_required
def cambiar_rol(usuario_id):
    if usuario_id == session['user_id']:
        flash('No puedes cambiar tu propio rol.', 'danger')
        return redirect(url_for('gestionar_usuarios'))
    nuevo_rol = request.form['rol']
    if nuevo_rol not in ['admin', 'empleado']:
        flash('Rol no válido.', 'danger')
        return redirect(url_for('gestionar_usuarios'))
    conn = get_db_connection()
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute('SELECT username FROM usuarios WHERE id = %s AND empresa_id = %s', (usuario_id, session['empresa_id']))
        user_to_change = cur.fetchone()
        if user_to_change:
            cur.execute('UPDATE usuarios SET rol = %s WHERE id = %s', (nuevo_rol, usuario_id))
            conn.commit()
            registrar_actividad('ROL_CAMBIADO', f"Cambió el rol del usuario '{user_to_change['username']}' (ID: {usuario_id}) a '{nuevo_rol}'.")
            flash('Rol de usuario actualizado con éxito.', 'success')
        else:
            flash('Usuario no encontrado.', 'danger')
    conn.close()
    return redirect(url_for('gestionar_usuarios'))

@app.route('/admin/eliminar_usuario/<int:usuario_id>', methods=['POST'])
@login_required
@admin_required
def eliminar_usuario(usuario_id):
    if usuario_id == session['user_id']:
        flash('No puedes eliminarte a ti mismo.', 'danger')
        return redirect(url_for('gestionar_usuarios'))
    conn = get_db_connection()
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute('SELECT username FROM usuarios WHERE id = %s AND empresa_id = %s', (usuario_id, session['empresa_id']))
        user_to_delete = cur.fetchone()
        if user_to_delete:
            cur.execute('DELETE FROM usuarios WHERE id = %s', (usuario_id,))
            conn.commit()
            registrar_actividad('USUARIO_ELIMINADO', f"Eliminó al usuario '{user_to_delete['username']}' (ID: {usuario_id}).")
            flash('Usuario eliminado con éxito.', 'success')
        else: flash('Usuario no encontrado.', 'danger')
    conn.close()
    return redirect(url_for('gestionar_usuarios'))

@app.route('/admin/historial')
@login_required
@admin_required
def ver_historial():
    conn = get_db_connection()
    page = request.args.get('page', 1, type=int)
    offset = (page - 1) * PER_PAGE
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute('SELECT COUNT(id) AS total FROM historial_actividad WHERE empresa_id = %s', (session['empresa_id'],))
        total_items = cur.fetchone()['total'] or 0
        total_pages = math.ceil(total_items / PER_PAGE)
        cur.execute('SELECT * FROM historial_actividad WHERE empresa_id = %s ORDER BY fecha DESC LIMIT %s OFFSET %s',
                    (session['empresa_id'], PER_PAGE, offset))
        historial = cur.fetchall()
    conn.close()
    return render_template('admin_historial.html', historial=historial, page=page, total_pages=total_pages)

@app.route('/pos')
@login_required
def pos(): return render_template('pos.html')

@app.route('/api/buscar_productos')
@login_required
def buscar_productos_api():
    query = request.args.get('q', '').strip()
    if not query: return jsonify([])
    conn = get_db_connection()
    if not conn: return jsonify({'error': 'Fallo en la conexión a la base de datos'}), 500
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            search_term = f"%{query}%"
            cur.execute('SELECT id, nombre, precio, cantidad FROM productos WHERE empresa_id = %s AND activo = TRUE AND (nombre ILIKE %s OR marca ILIKE %s) LIMIT 10',
                        (session['empresa_id'], search_term, search_term))
            productos = cur.fetchall()
        return jsonify([dict(row) for row in productos])
    except psycopg2.Error as e:
        print(f"Error en API de búsqueda: {e}")
        return jsonify({'error': 'Ocurrió un error en la base de datos'}), 500
    finally:
        if conn: conn.close()

@app.route('/api/actualizar_stock/<int:producto_id>', methods=['POST'])
@login_required
def actualizar_stock(producto_id):
    data = request.get_json()
    action = data.get('action')
    if not action or action not in ['incrementar', 'decrementar']: return jsonify({'success': False, 'message': 'Acción no válida.'}), 400
    conn = get_db_connection()
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute('SELECT nombre, cantidad FROM productos WHERE id = %s AND empresa_id = %s', (producto_id, session['empresa_id']))
        producto = cur.fetchone()
        if producto is None:
            conn.close()
            return jsonify({'success': False, 'message': 'Producto no encontrado.'}), 404
        nueva_cantidad = producto['cantidad']
        if action == 'incrementar': nueva_cantidad += 1
        elif action == 'decrementar' and nueva_cantidad > 0: nueva_cantidad -= 1
        cur.execute('UPDATE productos SET cantidad = %s WHERE id = %s AND empresa_id = %s', (nueva_cantidad, producto_id, session['empresa_id']))
    conn.commit()
    conn.close()
    registrar_actividad('STOCK_AJUSTADO', f"Ajustó el stock de '{producto['nombre']}' (ID: {producto_id}) de {producto['cantidad']} a {nueva_cantidad}.")
    return jsonify({'success': True, 'nueva_cantidad': nueva_cantidad})

@app.route('/procesar_venta', methods=['POST'])
@login_required
def procesar_venta():
    cart_json = request.form.get('cart_data')
    cliente_nombre, cliente_telefono = request.form.get('cliente_nombre', 'Cliente Contado'), request.form.get('cliente_telefono', '')
    if not cliente_nombre.strip(): cliente_nombre = 'Cliente Contado'
    if not cart_json:
        flash('El carrito está vacío.', 'danger')
        return redirect(url_for('pos'))
    cart_data = json.loads(cart_json)
    empresa_id, usuario_id, transaccion_id = session['empresa_id'], session['user_id'], str(uuid.uuid4())
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            total_venta = 0
            for item_id, item_data in cart_data.items():
                producto_id, cantidad_vendida = int(item_id), int(item_data['quantity'])
                cur.execute('SELECT nombre, precio, cantidad FROM productos WHERE id = %s AND empresa_id = %s FOR UPDATE', (producto_id, empresa_id))
                producto = cur.fetchone()
                if producto['cantidad'] < cantidad_vendida: raise Exception(f"Stock insuficiente para: {producto['nombre']}")
                nueva_cantidad = producto['cantidad'] - cantidad_vendida
                cur.execute('UPDATE productos SET cantidad = %s WHERE id = %s', (nueva_cantidad, producto_id))
                precio_total_item = cantidad_vendida * producto['precio']
                total_venta += precio_total_item
                cur.execute('INSERT INTO ventas (transaccion_id, empresa_id, producto_id, usuario_id, cantidad, precio_total, cliente_nombre, cliente_telefono) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
                             (transaccion_id, empresa_id, producto_id, usuario_id, cantidad_vendida, precio_total_item, cliente_nombre, cliente_telefono))
        conn.commit()
        registrar_actividad('VENTA_REGISTRADA', f"Registró la venta #{transaccion_id[:8]} para '{cliente_nombre}' por un total de ${total_venta:.2f}.")
        return redirect(url_for('mostrar_factura', transaccion_id=transaccion_id))
    except Exception as e:
        conn.rollback()
        flash(f"Error al procesar la venta: {e}", 'danger')
        return redirect(url_for('pos'))
    finally:
        conn.close()

@app.route('/factura/<string:transaccion_id>')
@login_required
def mostrar_factura(transaccion_id):
    conn = get_db_connection()
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute('SELECT v.cantidad, v.precio_total, v.cliente_nombre, v.cliente_telefono, p.nombre FROM ventas v JOIN productos p ON v.producto_id = p.id WHERE v.transaccion_id = %s AND v.empresa_id = %s', (transaccion_id, session['empresa_id']))
        items_vendidos = cur.fetchall()
        if not items_vendidos:
            flash('Factura no encontrada.', 'danger')
            conn.close()
            return redirect(url_for('pos'))
        cur.execute('SELECT * FROM empresas WHERE id = %s', (session['empresa_id'],))
        empresa = cur.fetchone()
        cur.execute('SELECT fecha_venta FROM ventas WHERE transaccion_id = %s LIMIT 1', (transaccion_id,))
        primera_venta = cur.fetchone()
    conn.close()
    total_general = sum(item['precio_total'] for item in items_vendidos)
    cliente_nombre, cliente_telefono = items_vendidos[0]['cliente_nombre'], items_vendidos[0]['cliente_telefono']
    fecha_formateada = primera_venta['fecha_venta'].strftime('%Y-%m-%d')
    return render_template('factura.html',
                           transaccion_id=transaccion_id,
                           items_vendidos=items_vendidos,
                           empresa=empresa,
                           fecha_venta=fecha_formateada,
                           total_general=total_general,
                           cliente_nombre=cliente_nombre,
                           cliente_telefono=cliente_telefono)