import os
import psycopg2
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

load_dotenv() # Carga las variables del archivo .env

DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise Exception("No se encontró la variable de entorno DATABASE_URL. Asegúrate de que tu archivo .env esté configurado.")

connection = psycopg2.connect(DATABASE_URL)

# Ejecuta el schema.sql para limpiar y crear las tablas
with open('schema.sql') as f:
    connection.cursor().execute(f.read())

cur = connection.cursor()

# 1. Crear TU empresa administradora del sistema
cur.execute("INSERT INTO empresas (nombre_empresa, direccion, telefono, rnc) VALUES (%s, %s, %s, %s) RETURNING id",
            ('InvenSys Corp', 'Plataforma Central', 'N/A', 'N/A') )
id_empresa_sistema = cur.fetchone()[0]

# 2. Crear TU cuenta de SUPERADMIN para esa empresa
# ¡IMPORTANTE! Cambia 'superadmin_password_seguro' por una contraseña fuerte que solo tú conozcas.
superadmin_password = generate_password_hash('superadmin_password_seguro')
cur.execute("INSERT INTO usuarios (empresa_id, username, password, rol) VALUES (%s, %s, %s, %s)",
            (id_empresa_sistema, 'superadmin', superadmin_password, 'superadmin')
            )

# 3. (Opcional) Podemos añadir una segunda empresa de muestra para tener algo que gestionar
cur.execute("INSERT INTO empresas (nombre_empresa, direccion, telefono, rnc) VALUES (%s, %s, %s, %s) RETURNING id",
            ('Tienda de Ejemplo', 'Calle Falsa 123', '809-123-4567', '1-30-09876-5') )
id_empresa_ejemplo = cur.fetchone()[0]

admin_ejemplo_password = generate_password_hash('admin123')
cur.execute("INSERT INTO usuarios (empresa_id, username, password, rol) VALUES (%s, %s, %s, %s)",
            (id_empresa_ejemplo, 'admin_tienda', admin_ejemplo_password, 'admin'))

cur.execute("INSERT INTO productos (empresa_id, nombre, marca, modelo, precio, cantidad) VALUES (%s, %s, %s, %s, %s, %s)",
            (id_empresa_ejemplo, 'Laptop Gamer Nitro 5', 'Acer', 'AN515-58', 1250.00, 8))


connection.commit()
cur.close()
connection.close()

print("Base de datos inicializada con cuenta de Superadmin y empresa de ejemplo.")