# init_db.py (Versión PostgreSQL)
import os
import psycopg2
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

load_dotenv() # Carga las variables del archivo .env

DATABASE_URL = os.environ.get('DATABASE_URL')
connection = psycopg2.connect(DATABASE_URL)

with open('schema.sql') as f:
    connection.cursor().execute(f.read())

cur = connection.cursor()

# PostgreSQL usa RETURNING id para obtener el ID recién insertado
cur.execute("INSERT INTO empresas (nombre_empresa, direccion, telefono, rnc) VALUES (%s, %s, %s, %s) RETURNING id",
            ('Tienda de Muestra, S.R.L.', 'Av. Principal 123, Santo Domingo', '809-555-1234', '1-01-12345-6') )
id_empresa_muestra = cur.fetchone()[0]

admin_password = generate_password_hash('admin123')
cur.execute("INSERT INTO usuarios (empresa_id, username, password, rol) VALUES (%s, %s, %s, %s)",
            (id_empresa_muestra, 'admin', admin_password, 'admin'))

cur.execute("INSERT INTO productos (empresa_id, nombre, marca, modelo, precio, cantidad) VALUES (%s, %s, %s, %s, %s, %s)",
            (id_empresa_muestra, 'Laptop Gamer Nitro 5', 'Acer', 'AN515-58', 1250.00, 8))

connection.commit()
cur.close()
connection.close()

print("Base de datos PostgreSQL inicializada con éxito.")