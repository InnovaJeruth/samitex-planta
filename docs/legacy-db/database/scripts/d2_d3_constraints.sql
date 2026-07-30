-- ============================================================
-- D2: UniqueConstraint en OFFaseTiempos (of_id + fase_id)
-- D3: FK formal para fase_id en tablas de fases
-- Ejecutar en SQL Server Management Studio contra SAMITEX-PLANTA
-- ============================================================

-- D2: Evita múltiples filas por OF + fase en of_fase_tiempos
ALTER TABLE of_fase_tiempos
ADD CONSTRAINT uq_of_fase_tiempos UNIQUE (of_id, fase_id);

-- D3: FK fase_id en of_fase_tiempos → fases_catalogo
ALTER TABLE of_fase_tiempos
ADD CONSTRAINT fk_of_fase_tiempos_fase_id
FOREIGN KEY (fase_id) REFERENCES fases_catalogo(fase_id);

-- D3: FK fase_id en of_fases_estado → fases_catalogo
ALTER TABLE of_fases_estado
ADD CONSTRAINT fk_of_fases_estado_fase_id
FOREIGN KEY (fase_id) REFERENCES fases_catalogo(fase_id);

-- D3: FK fase_id en of_fase_paradas → fases_catalogo
ALTER TABLE of_fase_paradas
ADD CONSTRAINT fk_of_fase_paradas_fase_id
FOREIGN KEY (fase_id) REFERENCES fases_catalogo(fase_id);

-- D3: FK fase_id en avance_registros → fases_catalogo
ALTER TABLE avance_registros
ADD CONSTRAINT fk_avance_registros_fase_id
FOREIGN KEY (fase_id) REFERENCES fases_catalogo(fase_id);
