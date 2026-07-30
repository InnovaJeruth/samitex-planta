"""MÓDULO ELIMINADO — Bot de Telegram (obsoleto).

El bot de Telegram fue retirado: el Chat analítico (RAG Text-to-SQL) lo
reemplaza. Este archivo quedó vacío a propósito.

Motivo técnico (auditoría de asincronía): el webhook era `async def` pero
dentro llamaba a Gemini de forma SÍNCRONA/bloqueante, lo que congelaba el
event loop de toda la app. Ya no existe router ni endpoints aquí.

Puedes borrar este archivo del proyecto cuando quieras; nada lo importa.
"""
