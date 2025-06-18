DROP TABLE IF EXISTS ventas;
DROP TABLE IF EXISTS productos;
DROP TABLE IF EXISTS historial_actividad; -- Se añade la nueva tabla aquí
DROP TABLE IF EXISTS usuarios;
DROP TABLE IF EXISTS empresas;

CREATE TABLE empresas (
    id SERIAL PRIMARY KEY,
    nombre_empresa TEXT UNIQUE NOT NULL,
    direccion TEXT,
    telefono TEXT,
    rnc TEXT,
    creado TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    empresa_id INTEGER NOT NULL REFERENCES empresas(id),
    username TEXT NOT NULL,
    password TEXT NOT NULL,
    rol TEXT NOT NULL DEFAULT 'empleado',
    creado TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (empresa_id, username)
);

CREATE TABLE productos (
    id SERIAL PRIMARY KEY,
    empresa_id INTEGER NOT NULL REFERENCES empresas(id),
    nombre TEXT NOT NULL,
    marca TEXT NOT NULL,
    modelo TEXT NOT NULL,
    precio NUMERIC(10, 2) NOT NULL,
    cantidad INTEGER NOT NULL,
    creado TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (empresa_id) REFERENCES empresas(id)
);

CREATE TABLE ventas (
    id SERIAL PRIMARY KEY,
    transaccion_id UUID NOT NULL,
    empresa_id INTEGER NOT NULL REFERENCES empresas(id),
    producto_id INTEGER NOT NULL REFERENCES productos(id),
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    cantidad INTEGER NOT NULL,
    precio_total NUMERIC(10, 2) NOT NULL,
    cliente_nombre TEXT,
    cliente_telefono TEXT,
    fecha_venta TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE historial_actividad (
    id SERIAL PRIMARY KEY,
    empresa_id INTEGER NOT NULL REFERENCES empresas(id),
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    usuario_username TEXT NOT NULL,
    accion TEXT NOT NULL,
    descripcion TEXT,
    fecha TIMESTAMPTZ NOT NULL DEFAULT NOW()
);