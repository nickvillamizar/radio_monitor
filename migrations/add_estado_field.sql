-- Migration: Add estado field to emisoras table
ALTER TABLE emisoras 
ADD COLUMN estado VARCHAR(20) NOT NULL DEFAULT 'activo_hoy';

CREATE INDEX idx_emisoras_estado ON emisoras(estado);
