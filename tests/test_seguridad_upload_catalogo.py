"""Auditoría DevSecOps · validación de contenido en subida de documentos de catálogo."""
from app.routers.catalogo import _magic_doc_ok


def test_pdf_valido_pasa():
    assert _magic_doc_ok(b"%PDF-1.7\n...", ".pdf") is True


def test_pdf_falso_se_rechaza():
    # extensión .pdf pero contenido HTML/script → rechazado
    assert _magic_doc_ok(b"<html><script>alert(1)</script>", ".pdf") is False


def test_office_docx_zip():
    assert _magic_doc_ok(b"PK\x03\x04....", ".docx") is True
    assert _magic_doc_ok(b"noesunzip", ".xlsx") is False


def test_jpg_firma():
    assert _magic_doc_ok(b"\xff\xd8\xff\xe0resto", ".jpg") is True
    assert _magic_doc_ok(b"GIF89a", ".jpg") is False


def test_dxf_texto_sin_firma_pasa():
    # .dxf es texto → no se verifica firma
    assert _magic_doc_ok(b"  0\nSECTION\n", ".dxf") is True
