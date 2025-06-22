import os
import psycopg2
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise Exception("No se encontró la variable de entorno DATABASE_URL. Asegúrate de que tu archivo .env esté configurado.")

connection = psycopg2.connect(DATABASE_URL)

with open('schema.sql') as f:
    connection.cursor().execute(f.read())

cur = connection.cursor()

# 1. Crear una empresa de muestra
cur.execute("INSERT INTO empresas (nombre_empresa, direccion, telefono, rnc) VALUES (%s, %s, %s, %s) RETURNING id",
            ('Tienda de Muestra, S.R.L.', 'Av. Principal 123, Santo Domingo', '809-555-1234', '1-01-12345-6') )
id_empresa_muestra = cur.fetchone()[0]

# 2. Crear un usuario admin para esa empresa
admin_password = generate_password_hash('admin123')
cur.execute("INSERT INTO usuarios (empresa_id, username, password, rol) VALUES (%s, %s, %s, %s)",
            (id_empresa_muestra, 'admin', admin_password, 'admin'))

# 3. Añadir productos de muestra para esa empresa
cur.execute("INSERT INTO productos (empresa_id, nombre, marca, modelo, precio, cantidad) VALUES (%s, %s, %s, %s, %s, %s)",
            (id_empresa_muestra, 'Laptop Gamer Nitro 5', 'Acer', 'AN515-58', 1250.00, 8))
cur.execute("INSERT INTO productos (empresa_id, nombre, marca, modelo, precio, cantidad) VALUES (%s, %s, %s, %s, %s, %s)",
            (id_empresa_muestra, 'Monitor Curvo Odyssey G5', 'Samsung', 'LC27G55T', 350.50, 15))
cur.execute("INSERT INTO productos (empresa_id, nombre, marca, modelo, precio, cantidad) VALUES (%s, %s, %s, %s, %s, %s)",
            (id_empresa_muestra, 'Teclado Mecánico K2', 'Keychron', 'K2-C3', 95.99, 4))

# --- LÍNEA CORREGIDA ---
# Usamos 'False' de Python en lugar de 'FALSE' de SQL
cur.execute("INSERT INTO productos (empresa_id, nombre, marca, modelo, precio, cantidad, activo) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (id_empresa_muestra, 'Mouse Viejo', 'Genius', 'X100', 10.00, 0, False))

connection.commit()
cur.close()
connection.close()

print("Base de datos PostgreSQL inicializada con éxito.")