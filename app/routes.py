
from flask import Flask, render_template, request, redirect, url_for, flash, session
from app import app, mysql
from werkzeug.security import generate_password_hash, check_password_hash

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/registro_unificado', methods=['GET', 'POST'])
def registro_usuario():
    if request.method == 'POST':
        tipo = request.form['tipo_usuario']  # "cliente" o "admin"
        nombre = request.form['nombre']
        correo = request.form['correo']
        password = request.form['password']
        password_segura = generate_password_hash(password)

        cur = mysql.connection.cursor()

        # ✅ Verificar si el correo ya existe
        cur.execute("SELECT id FROM usuarios WHERE correo = %s", (correo,))
        usuario_existente = cur.fetchone()
        if usuario_existente:
            flash("Ya existe un usuario registrado con ese correo electrónico.", "danger")
            return redirect(url_for('registro_usuario'))

        # ✅ Si no existe, lo insertamos
        cur.execute("""
            INSERT INTO usuarios (nombre_completo, correo, contraseña, tipo_usuario)
            VALUES (%s, %s, %s, %s)
        """, (nombre, correo, password_segura, tipo))
        mysql.connection.commit()
        cur.close()

        flash("Usuario registrado correctamente.", "success")
        return redirect(url_for('index'))

    return render_template('registro_unificado.html')



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form['correo']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM Usuarios WHERE correo = %s", (correo,))
        usuario = cur.fetchone()
        cur.close()

        print("Usuario encontrado:", usuario)
        print("Contraseña ingresada:", password)

        if usuario and check_password_hash(usuario['contraseña'], password):
            print("Contraseña correcta")
            session['usuario_id'] = usuario['id']
            session['tipo_usuario'] = usuario['tipo_usuario']

            if usuario['tipo_usuario'] == 'admin':
                print("Redirigiendo a panel de administrador")
                return redirect(url_for('admin_dashboard'))
            else:
                print("Redirigiendo al catálogo")
                return redirect(url_for('catalogo'))
        else:
            print("Credenciales incorrectas")
            flash('Credenciales incorrectas.', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')



@app.route('/probar-conexion')
def probar_conexion():
    try:
        cur = mysql.connection.cursor()
        cur.execute("SHOW TABLES;")
        tablas = cur.fetchall()
        cur.close()
        return f"Conexión exitosa. Tablas encontradas: {', '.join([list(t.values())[0] for t in tablas])}"
    except Exception as e:
        return f"Error al conectar a la base de datos: {e}"


@app.route('/admin-dashboard')
def admin_dashboard():
    if 'usuario_id' in session and session.get('tipo_usuario') == 'admin':
        return redirect(url_for('admin_productos'))  # redirige a /admin/productos
    return redirect(url_for('login'))


@app.route('/catalogo')
def catalogo():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM Productos")
    productos = cur.fetchall()
    cur.close()
    print("Productos cargados:", len(productos))
    return render_template('catalogo.html', productos=productos)


@app.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada correctamente.', 'info')
    return redirect(url_for('index'))  # Ahora redirige a la página principal



@app.route('/agregar-carrito/<int:producto_id>', methods=['POST'])
def agregar_carrito(producto_id):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    cantidad = int(request.form.get('cantidad', 1))
    usuario_id = session['usuario_id']

    cur = mysql.connection.cursor()

    # Verificar stock disponible
    cur.execute("SELECT stock FROM productos WHERE id = %s", (producto_id,))
    producto = cur.fetchone()
    if not producto or producto['stock'] < cantidad:
        flash("No hay suficiente stock disponible.", "danger")
        return redirect(url_for('catalogo'))

    # Insertar o actualizar carrito
    cur.execute("SELECT id, cantidad FROM carrito WHERE usuario_id = %s AND producto_id = %s", (usuario_id, producto_id))
    item = cur.fetchone()

    if item:
        nueva_cantidad = item['cantidad'] + cantidad
        cur.execute("UPDATE carrito SET cantidad = %s WHERE id = %s", (nueva_cantidad, item['id']))
    else:
        cur.execute("INSERT INTO carrito (usuario_id, producto_id, cantidad) VALUES (%s, %s, %s)", (usuario_id, producto_id, cantidad))

    # Actualizar stock
    nuevo_stock = producto['stock'] - cantidad
    cur.execute("UPDATE productos SET stock = %s WHERE id = %s", (nuevo_stock, producto_id))

    mysql.connection.commit()
    cur.close()
    flash('Producto agregado al carrito.')
    return redirect(url_for('catalogo'))



@app.route('/carrito')
def ver_carrito():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    usuario_id = session['usuario_id']
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT c.id, p.nombre, p.precio, c.cantidad, (p.precio * c.cantidad) AS total
        FROM Carrito c
        JOIN Productos p ON c.producto_id = p.id
        WHERE c.usuario_id = %s
    """, (usuario_id,))
    items = cur.fetchall()
    cur.close()

    total_general = sum(item['total'] for item in items)
    return render_template('carrito.html', items=items, total=total_general)

@app.route('/carrito/actualizar/<int:id>', methods=['POST'])
def actualizar_carrito(id):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    nueva_cantidad = int(request.form['nueva_cantidad'])

    cur = mysql.connection.cursor()

    # Obtener la cantidad actual y el producto
    cur.execute("SELECT producto_id, cantidad FROM carrito WHERE id = %s", (id,))
    item = cur.fetchone()

    if not item:
        flash("Producto no encontrado.", "danger")
        return redirect(url_for('ver_carrito'))

    producto_id = item['producto_id']
    cantidad_actual = item['cantidad']

    # Obtener stock actual
    cur.execute("SELECT stock FROM productos WHERE id = %s", (producto_id,))
    producto = cur.fetchone()
    stock_actual = producto['stock']

    diferencia = nueva_cantidad - cantidad_actual

    if diferencia > 0:
        if stock_actual < diferencia:
            flash("No hay suficiente stock disponible.", "danger")
            return redirect(url_for('ver_carrito'))
        cur.execute("UPDATE productos SET stock = stock - %s WHERE id = %s", (diferencia, producto_id))
    elif diferencia < 0:
        cur.execute("UPDATE productos SET stock = stock + %s WHERE id = %s", (-diferencia, producto_id))

    # Actualizar carrito
    cur.execute("UPDATE carrito SET cantidad = %s WHERE id = %s", (nueva_cantidad, id))

    mysql.connection.commit()
    cur.close()

    flash("Cantidad actualizada.", "success")
    return redirect(url_for('ver_carrito'))


@app.route('/carrito/eliminar/<int:id>', methods=['POST'])
def eliminar_del_carrito(id):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM carrito WHERE id = %s", (id,))
    mysql.connection.commit()
    cur.close()

    flash("Producto eliminado del carrito.")
    return redirect(url_for('ver_carrito'))



@app.route('/admin/productos')
def admin_productos():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM productos")
    productos = cur.fetchall()
    cur.close()
    return render_template('admin.html', productos=productos)



@app.route('/admin/productos/agregar', methods=['POST'])
def agregar_producto():
    nombre = request.form['nombre']
    descripcion = request.form.get('descripcion', '')
    precio = request.form['precio']
    stock = request.form['stock']
    imagen = request.form['imagen']

    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO productos (nombre, descripcion, precio, imagen, stock)
        VALUES (%s, %s, %s, %s, %s)
    """, (nombre, descripcion, precio, imagen, stock))
    mysql.connection.commit()
    cur.close()

    flash('Producto agregado con éxito')
    return redirect(url_for('admin_productos'))




@app.route('/admin/productos/actualizar/<int:id>', methods=['POST'])
def actualizar_producto(id):
    nombre = request.form['nombre']
    descripcion = request.form.get('descripcion', '')
    precio = request.form['precio']
    stock = request.form['stock']
    imagen = request.form['imagen']

    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE productos SET nombre=%s, descripcion=%s, precio=%s, imagen=%s, stock=%s
        WHERE id=%s
    """, (nombre, descripcion, precio, imagen, stock, id))
    mysql.connection.commit()
    cur.close()

    flash('Producto actualizado')
    return redirect(url_for('admin_productos'))



@app.route('/admin/productos/editar/<int:id>', methods=['GET', 'POST'])
def editar_producto(id):
    # Buscar el producto por su ID
    producto = next((p for p in productos if p['id'] == id), None)
    if producto is None:
        return "Producto no encontrado", 404

    if request.method == 'POST':
        producto['nombre'] = request.form['nombre']
        producto['precio'] = request.form['precio']
        producto['imagen'] = request.form['imagen']
        return redirect(url_for('admin_productos'))

    return render_template('editar_producto.html', producto=producto)

@app.route('/admin/productos/eliminar/<int:id>', methods=['POST'])
def eliminar_producto(id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM productos WHERE id=%s", (id,))
        mysql.connection.commit()
        cur.close()
        flash('Producto eliminado')
    except Exception as e:
        flash(f'Error al eliminar: {e}', 'danger')

    return redirect(url_for('admin_productos'))


@app.route('/finalizar-compra', methods=['GET', 'POST'])
def finalizar_compra():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    usuario_id = session['usuario_id']

    # Obtener productos del carrito
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT c.id, p.nombre, p.precio, c.cantidad, (p.precio * c.cantidad) AS total
        FROM Carrito c
        JOIN Productos p ON c.producto_id = p.id
        WHERE c.usuario_id = %s
    """, (usuario_id,))
    items = cur.fetchall()

    total = round(sum(item['total'] for item in items), 2)

    if request.method == 'POST':
        metodo_pago = request.form['metodo_pago']

        if metodo_pago == 'Tarjeta':
            numero = request.form.get('numero_tarjeta')
            cvv = request.form.get('cvv')
            expiracion = request.form.get('expiracion')
            if not numero or not cvv or not expiracion:
                flash("Todos los campos de la tarjeta son obligatorios.", "danger")
                return redirect(url_for('finalizar_compra'))
        
        elif metodo_pago == 'Nequi':
            numero_nequi = request.form.get('numero_nequi')
            if not numero_nequi:
                flash("Debes ingresar tu número de Nequi.", "danger")
                return redirect(url_for('finalizar_compra'))
       
        elif metodo_pago == 'Daviplata':
            numero_daviplata = request.form.get('numero_daviplata')
            if not numero_daviplata:
                flash("Debes ingresar tu número de Daviplata.", "danger")
                return redirect(url_for('finalizar_compra'))
        else:
            flash("Selecciona un método de pago válido.", "danger")
            return redirect(url_for('finalizar_compra'))
        
        # Limpiar carrito después del pago
        cur.execute("DELETE FROM carrito WHERE usuario_id = %s", (usuario_id,))
        mysql.connection.commit()
        cur.close()

        flash(f'Compra finalizada con método de pago: {metodo_pago}', 'success')
        return redirect(url_for('compra_exitosa'))

    return render_template('finalizar_compra.html', items=items, total=total)



@app.route('/confirmar-pago', methods=['POST'])
def confirmar_pago():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    metodo = request.form.get('metodo_pago')
    usuario_id = session['usuario_id']

    cur = mysql.connection.cursor()

    # Obtener items del carrito antes de borrar
    cur.execute("""
        SELECT p.id, p.stock, c.cantidad FROM Carrito c
        JOIN Productos p ON c.producto_id = p.id
        WHERE c.usuario_id = %s
    """, (usuario_id,))
    items = cur.fetchall()

    # Actualizar stock si hiciste rollback antes
    for item in items:
        nuevo_stock = item['stock'] - item['cantidad']
        if nuevo_stock < 0:
            flash("Error de stock. No hay unidades suficientes.", "danger")
            return redirect(url_for('ver_carrito'))

        cur.execute("UPDATE productos SET stock = %s WHERE id = %s", (nuevo_stock, item['id']))

    # Vaciar carrito
    cur.execute("DELETE FROM carrito WHERE usuario_id = %s", (usuario_id,))
    mysql.connection.commit()
    cur.close()

    flash(f"Compra realizada con éxito usando método: {metodo.upper()}", "success")
    return redirect(url_for('catalogo'))

@app.route('/compra_exitosa')
def compra_exitosa():
    return render_template('compra_exitosa.html')

@app.route('/admin/registrar-admin', methods=['GET', 'POST'])
def registrar_admin():
    if 'usuario_id' not in session or session.get('tipo_usuario') != 'admin':
        flash("Acceso no autorizado", "danger")
        return redirect(url_for('login'))

    if request.method == 'POST':
        nombre = request.form['nombre']
        correo = request.form['correo']
        password = request.form['password']
        codigo_admin = request.form['codigo_admin']

        # Validar que el código esté registrado
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM admin_codes WHERE codigo = %s", (codigo_admin,))
        resultado = cur.fetchone()

        if not resultado:
            flash("Código de administrador no válido", "danger")
            return redirect(url_for('registrar_admin'))

        password_segura = generate_password_hash(password)

        cur.execute("""
            INSERT INTO usuarios (nombre_completo, correo, contraseña, tipo_usuario)
            VALUES (%s, %s, %s, %s)
        """, (nombre, correo, password_segura, 'admin'))

        mysql.connection.commit()
        cur.close()

        flash("Administrador registrado correctamente", "success")
        return redirect(url_for('registrar_admin'))

    return render_template('registrar_admin.html')


























