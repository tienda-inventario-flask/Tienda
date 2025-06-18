import sqlite3
from werkzeug.security import generate_password_hash

connection = sqlite3.connect('database.db')
with open('schema.sql') as f: connection.executescript(f.read())
cur = connection.cursor()

cur.execute("INSERT INTO empresas (nombre_empresa, direccion, telefono, rnc) VALUES (?, ?, ?, ?)",
            ('Tienda de Muestra, S.R.L.', 'Av. Principal 123, Santo Domingo', '809-555-1234', '1-01-12345-6') )
id_empresa_muestra = cur.lastrowid

admin_password = generate_password_hash('admin123')
cur.execute("INSERT INTO usuarios (empresa_id, username, password, rol) VALUES (?, ?, ?, ?)", (id_empresa_muestra, 'admin', admin_password, 'admin'))
cur.execute("INSERT INTO productos (empresa_id, nombre, marca, modelo, precio, cantidad) VALUES (?, ?, ?, ?, ?, ?)", (id_empresa_muestra, 'Laptop Gamer Nitro 5', 'Acer', 'AN515-58', 1250.00, 8))
connection.commit()
connection.close()
print("Base de datos inicializada con empresa de muestra y usuario admin.")