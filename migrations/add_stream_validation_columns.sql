-- archivo: migrations/add_stream_validation_columns.sql
-- Script para agregar columnas de validación a la tabla emisoras
-- 
-- Ejecute esto si está usando una base de datos existente
-- Nota: Si usa SQLAlchemy con Flask-Migrate, esto se hará automáticamente

-- Opción 1: PostgreSQL (Neon)
-- =====================================================

ALTER TABLE emisoras
ADD COLUMN url_valida BOOLEAN DEFAULT TRUE;

ALTER TABLE emisoras
ADD COLUMN es_stream_activo BOOLEAN DEFAULT TRUE;

ALTER TABLE emisoras
ADD COLUMN ultima_validacion TIMESTAMP;

ALTER TABLE emisoras
ADD COLUMN diagnostico VARCHAR(500);

-- Crear índices para mejor performance
CREATE INDEX idx_url_valida ON emisoras(url_valida);
CREATE INDEX idx_es_stream_activo ON emisoras(es_stream_activo);
CREATE INDEX idx_ultima_validacion ON emisoras(ultima_validacion);


-- Opción 2: SQLite (desarrollo local)
-- =====================================================

ALTER TABLE emisoras
ADD COLUMN url_valida BOOLEAN DEFAULT 1;

ALTER TABLE emisoras
ADD COLUMN es_stream_activo BOOLEAN DEFAULT 1;

ALTER TABLE emisoras
ADD COLUMN ultima_validacion DATETIME;

ALTER TABLE emisoras
ADD COLUMN diagnostico VARCHAR(500);


-- Opción 3: MySQL
-- =====================================================

ALTER TABLE emisoras
ADD COLUMN url_valida BOOLEAN DEFAULT TRUE;

ALTER TABLE emisoras
ADD COLUMN es_stream_activo BOOLEAN DEFAULT TRUE;

ALTER TABLE emisoras
ADD COLUMN ultima_validacion DATETIME;

ALTER TABLE emisoras
ADD COLUMN diagnostico VARCHAR(500);

CREATE INDEX idx_url_valida ON emisoras(url_valida);
CREATE INDEX idx_es_stream_activo ON emisoras(es_stream_activo);
CREATE INDEX idx_ultima_validacion ON emisoras(ultima_validacion);


-- Verificar que las columnas se crearon correctamente
-- =====================================================

-- PostgreSQL
SELECT column_name, data_type FROM information_schema.columns 
WHERE table_name = 'emisoras' 
ORDER BY ordinal_position;

-- SQLite
PRAGMA table_info(emisoras);

-- MySQL
DESCRIBE emisoras;
