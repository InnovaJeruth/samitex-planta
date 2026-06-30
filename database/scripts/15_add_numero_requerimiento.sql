-- Migración 15: agregar numero_requerimiento a of_fase_paradas
ALTER TABLE of_fase_paradas
    ADD numero_requerimiento VARCHAR(50) NULL;
