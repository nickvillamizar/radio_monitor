-- Migration: Add detection metadata fields to canciones table
ALTER TABLE canciones 
ADD COLUMN fuente VARCHAR(20) DEFAULT 'icy';

ALTER TABLE canciones 
ADD COLUMN razon_prediccion VARCHAR(200);

ALTER TABLE canciones 
ADD COLUMN confianza_prediccion FLOAT;

CREATE INDEX idx_canciones_fuente ON canciones(fuente);
