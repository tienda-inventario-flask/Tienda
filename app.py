import sqlite3, math, io, csv, json, uuid
from flask import make_response, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, request, redirect, url_for, flash, session
from functools import wraps

app = Flask(__name__)
app.secret_key = 'clave_secreta_super_dificil_de_adivinar_y_muy_larga_v5'
PER_PAGE = 5

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
        if session.get('rol') != 'admin':
            flash('No tienes permiso para realizar esta acción.', 'danger')
            return redirect(url_for('mostrar_inventario'))
        return f(*args, **kwargs)
    return decorated_function
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session: return redirect(url_for('mostrar_inventario'))
    if request.method == 'POST':
        username, password = request.form['username'], request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM usuarios WHERE username = ?', (username,)).fetchone()
        if user is None or not check_password_hash(user['password'], password):
            flash('Nombre de usuario o contraseña incorrectos.', 'danger')
            conn.close()
        else:
            empresa = conn.execute('SELECT nombre_empresa FROM empresas WHERE id = ?', (user['empresa_id'],)).fetchone()
            conn.close()
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['rol'] = user['rol']
            session['empresa_id'] = user['empresa_id']
            session['nombre_empresa'] = empresa['nombre_empresa']
            return redirect(url_for('mostrar_inventario'))
    return render_template('login.html')
@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if 'user_id' in session: return redirect(url_for('mostrar_inventario'))
    if request.method == 'POST':
        nombre_empresa = request.form['nombre_empresa']
        direccion = request.form.get('direccion', '')
        telefono = request.form.get('telefono', '')
        rnc = request.form.get('rnc', '')
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        empresa = conn.execute('SELECT id FROM empresas WHERE nombre_empresa = ?', (nombre_empresa,)).fetchone()
        if empresa:
            flash('Ya existe una empresa con ese nombre.', 'danger')
            conn.close()
            return redirect(url_for('registro'))
        cursor = conn.cursor()
        cursor.execute('INSERT INTO empresas (nombre_empresa, direccion, telefono, rnc) VALUES (?, ?, ?, ?)', (nombre_empresa, direccion, telefono, rnc))
        empresa_id = cursor.lastrowid
        hashed_password = generate_password_hash(password)
        cursor.execute('INSERT INTO usuarios (empresa_id, username, password, rol) VALUES (?, ?, ?, ?)', (empresa_id, username, hashed_password, 'admin'))
        conn.commit()
        conn.close()
        flash('¡Empresa y usuario administrador creados con éxito! Por favor, inicia sesión.', 'success')
        return redirect(url_for('login'))
    return render_template('registro.html')
@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión exitosamente.', 'success')
    return redirect(url_for('login'))
@app.route('/')
@login_required
def mostrar_inventario():
    empresa_id = session['empresa_id']
    page = request.args.get('page', 1, type=int)
    query = request.args.get('q')
    conn = get_db_connection()
    offset = (page - 1) * PER_PAGE
    base_where = ' WHERE empresa_id = ? '
    params = [empresa_id]
    if query:
        search_term = f"%{query}%"
        where_clause = base_where + ' AND (nombre LIKE ? OR marca LIKE ?)'
        params.extend([search_term, search_term])
    else: where_clause = base_where
    stats_query_total_productos = 'SELECT COUNT(id) FROM productos' + where_clause
    total_productos = conn.execute(stats_query_total_productos, params).fetchone()[0] or 0
    stats_query_total_stock = 'SELECT SUM(cantidad) FROM productos' + where_clause
    total_stock = conn.execute(stats_query_total_stock, params).fetchone()[0] or 0
    stats_query_valor_total = 'SELECT SUM(precio * cantidad) FROM productos' + where_clause
    valor_inventario = conn.execute(stats_query_valor_total, params).fetchone()[0] or 0
    total_pages = math.ceil(total_productos / PER_PAGE)
    main_query = 'SELECT * FROM productos' + where_clause + ' ORDER BY id DESC LIMIT ? OFFSET ?'
    final_params = params + [PER_PAGE, offset]
    productos = conn.execute(main_query, final_params).fetchall()
    conn.close()
    return render_template('index.html', inventario=productos, query=query, page=page, total_pages=total_pages, total_productos=total_productos, total_stock=total_stock, valor_inventario=valor_inventario, PER_PAGE=PER_PAGE)
def get_producto(producto_id):
    conn = get_db_connection()
    producto = conn.execute('SELECT * FROM productos WHERE id = ? AND empresa_id = ?', (producto_id, session['empresa_id'])).fetchone()
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
        conn.execute('INSERT INTO productos (empresa_id, nombre, marca, modelo, precio, cantidad) VALUES (?, ?, ?, ?, ?, ?)',(session['empresa_id'], nombre, marca, modelo, precio, cantidad))
        conn.commit()
        conn.close()
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
        conn.execute('UPDATE productos SET nombre = ?, marca = ?, modelo = ?, precio = ?, cantidad = ? WHERE id = ? AND empresa_id = ?',(nombre, marca, modelo, precio, cantidad, producto_id, session['empresa_id']))
        conn.commit()
        conn.close()
        flash('¡Producto actualizado correctamente!', 'success')
        return redirect(url_for('mostrar_inventario'))
    return render_template('editar_producto.html', producto=producto)
@app.route('/eliminar/<int:producto_id>')
@login_required
@admin_required
def eliminar_producto(producto_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM productos WHERE id = ? AND empresa_id = ?', (producto_id, session['empresa_id']))
    conn.commit()
    conn.close()
    flash('Producto eliminado.', 'danger')
    return redirect(url_for('mostrar_inventario'))
@app.route('/reportes')
@login_required
def reportes():
    conn = get_db_connection()
    empresa_id = session['empresa_id']
    top_stock_productos = conn.execute('SELECT nombre, cantidad FROM productos WHERE empresa_id = ? ORDER BY cantidad DESC LIMIT 5', (empresa_id,)).fetchall()
    stock_labels = [row['nombre'] for row in top_stock_productos]
    stock_data = [row['cantidad'] for row in top_stock_productos]
    productos_por_marca = conn.execute('SELECT marca, COUNT(id) as total FROM productos WHERE empresa_id = ? GROUP BY marca', (empresa_id,)).fetchall()
    marca_labels = [row['marca'] for row in productos_por_marca]
    marca_data = [row['total'] for row in productos_por_marca]
    conn.close()
    return render_template('reportes.html', stock_labels=json.dumps(stock_labels), stock_data=json.dumps(stock_data), marca_labels=json.dumps(marca_labels), marca_data=json.dumps(marca_data))
@app.route('/exportar_csv')
@login_required
def exportar_csv():
    conn = get_db_connection()
    productos = conn.execute('SELECT id, nombre, marca, modelo, precio, cantidad FROM productos WHERE empresa_id = ? ORDER BY id', (session['empresa_id'],)).fetchall()
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Nombre', 'Marca', 'Modelo', 'Precio', 'Cantidad en Stock'])
    for producto in productos: writer.writerow(producto)
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=inventario.csv'
    response.headers['Content-type'] = 'text/csv'
    return response
@app.route('/admin/usuarios')
@login_required
@admin_required
def gestionar_usuarios():
    conn = get_db_connection()
    usuarios = conn.execute('SELECT id, username, rol, creado FROM usuarios WHERE empresa_id = ? ORDER BY username', (session['empresa_id'],)).fetchall()
    conn.close()
    return render_template('admin_usuarios.html', usuarios=usuarios)
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
    conn.execute('UPDATE usuarios SET rol = ? WHERE id = ? AND empresa_id = ?', (nuevo_rol, usuario_id, session['empresa_id']))
    conn.commit()
    conn.close()
    flash('Rol de usuario actualizado con éxito.', 'success')
    return redirect(url_for('gestionar_usuarios'))
@app.route('/admin/eliminar_usuario/<int:usuario_id>')
@login_required
@admin_required
def eliminar_usuario(usuario_id):
    if usuario_id == session['user_id']:
        flash('No puedes eliminarte a ti mismo.', 'danger')
        return redirect(url_for('gestionar_usuarios'))
    conn = get_db_connection()
    conn.execute('DELETE FROM usuarios WHERE id = ? AND empresa_id = ?', (usuario_id, session['empresa_id']))
    conn.commit()
    conn.close()
    flash('Usuario eliminado con éxito.', 'success')
    return redirect(url_for('gestionar_usuarios'))
@app.route('/empresa/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_empresa():
    conn = get_db_connection()
    empresa_id = session['empresa_id']
    if request.method == 'POST':
        nombre_empresa, direccion, telefono, rnc = request.form['nombre_empresa'], request.form['direccion'], request.form['telefono'], request.form['rnc']
        if not nombre_empresa: flash('El nombre de la empresa no puede estar vacío.', 'danger')
        else:
            conn.execute('UPDATE empresas SET nombre_empresa = ?, direccion = ?, telefono = ?, rnc = ? WHERE id = ?', (nombre_empresa, direccion, telefono, rnc, empresa_id))
            conn.commit()
            session['nombre_empresa'] = nombre_empresa
            flash('Datos de la empresa actualizados con éxito.', 'success')
        conn.close()
        return redirect(url_for('editar_empresa'))
    empresa = conn.execute('SELECT * FROM empresas WHERE id = ?', (empresa_id,)).fetchone()
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
        user = conn.execute('SELECT password FROM usuarios WHERE id = ?', (session['user_id'],)).fetchone()
        if not check_password_hash(user['password'], password_actual):
            flash('La contraseña actual es incorrecta.', 'danger')
        else:
            hashed_password = generate_password_hash(nueva_password)
            conn.execute('UPDATE usuarios SET password = ? WHERE id = ?', (hashed_password, session['user_id']))
            conn.commit()
            flash('Contraseña actualizada con éxito.', 'success')
        conn.close()
        return redirect(url_for('cambiar_password'))
    return render_template('cambiar_password.html')
@app.route('/pos')
@login_required
def pos():
    return render_template('pos.html')
@app.route('/api/buscar_productos')
@login_required
def buscar_productos_api():
    query = request.args.get('q', '')
    if len(query) < 2: return jsonify([])
    conn = get_db_connection()
    search_term = f"%{query}%"
    productos = conn.execute('SELECT id, nombre, precio, cantidad FROM productos WHERE empresa_id = ? AND (nombre LIKE ? OR marca LIKE ?) LIMIT 10', (session['empresa_id'], search_term, search_term)).fetchall()
    conn.close()
    return jsonify([dict(row) for row in productos])
@app.route('/api/actualizar_stock/<int:producto_id>', methods=['POST'])
@login_required
def actualizar_stock(producto_id):
    data = request.get_json()
    action = data.get('action')
    if not action or action not in ['incrementar', 'decrementar']: return jsonify({'success': False, 'message': 'Acción no válida.'}), 400
    conn = get_db_connection()
    producto = conn.execute('SELECT cantidad FROM productos WHERE id = ? AND empresa_id = ?', (producto_id, session['empresa_id'])).fetchone()
    if producto is None:
        conn.close()
        return jsonify({'success': False, 'message': 'Producto no encontrado.'}), 404
    nueva_cantidad = producto['cantidad']
    if action == 'incrementar': nueva_cantidad += 1
    elif action == 'decrementar' and nueva_cantidad > 0: nueva_cantidad -= 1
    conn.execute('UPDATE productos SET cantidad = ? WHERE id = ? AND empresa_id = ?', (nueva_cantidad, producto_id, session['empresa_id']))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'nueva_cantidad': nueva_cantidad})
@app.route('/procesar_venta', methods=['POST'])
@login_required
def procesar_venta():
    cart_json = request.form.get('cart_data')
    cliente_nombre = request.form.get('cliente_nombre', 'Cliente Contado')
    cliente_telefono = request.form.get('cliente_telefono', '')
    if not cliente_nombre.strip(): cliente_nombre = 'Cliente Contado'
    if not cart_json:
        flash('El carrito está vacío.', 'danger')
        return redirect(url_for('pos'))
    cart_data = json.loads(cart_json)
    empresa_id, usuario_id = session['empresa_id'], session['user_id']
    transaccion_id = str(uuid.uuid4())
    conn = get_db_connection()
    try:
        for item_id, item_data in cart_data.items():
            producto_id, cantidad_vendida = int(item_id), int(item_data['quantity'])
            producto = conn.execute('SELECT nombre, precio, cantidad FROM productos WHERE id = ? AND empresa_id = ?', (producto_id, empresa_id)).fetchone()
            if producto['cantidad'] < cantidad_vendida: raise Exception(f"Stock insuficiente para: {producto['nombre']}")
            nueva_cantidad = producto['cantidad'] - cantidad_vendida
            conn.execute('UPDATE productos SET cantidad = ? WHERE id = ?', (nueva_cantidad, producto_id))
            precio_total = cantidad_vendida * producto['precio']
            conn.execute('INSERT INTO ventas (transaccion_id, empresa_id, producto_id, usuario_id, cantidad, precio_total, cliente_nombre, cliente_telefono) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                         (transaccion_id, empresa_id, producto_id, usuario_id, cantidad_vendida, precio_total, cliente_nombre, cliente_telefono))
        conn.commit()
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
    items_vendidos = conn.execute('SELECT v.cantidad, v.precio_total, v.cliente_nombre, v.cliente_telefono, p.nombre FROM ventas v JOIN productos p ON v.producto_id = p.id WHERE v.transaccion_id = ? AND v.empresa_id = ?',
                                (transaccion_id, session['empresa_id'])).fetchall()
    if not items_vendidos:
        flash('Factura no encontrada.', 'danger')
        return redirect(url_for('pos'))
    empresa = conn.execute('SELECT * FROM empresas WHERE id = ?', (session['empresa_id'],)).fetchone()
    primera_venta = conn.execute('SELECT fecha_venta FROM ventas WHERE transaccion_id = ?', (transaccion_id,)).fetchone()
    total_general = sum(item['precio_total'] for item in items_vendidos)
    conn.close()
    cliente_nombre, cliente_telefono = items_vendidos[0]['cliente_nombre'], items_vendidos[0]['cliente_telefono']
    return render_template('factura.html', transaccion_id=transaccion_id, items_vendidos=items_vendidos, empresa=empresa, fecha_venta=primera_venta['fecha_venta'].split(" ")[0], total_general=total_general, cliente_nombre=cliente_nombre, cliente_telefono=cliente_telefono)