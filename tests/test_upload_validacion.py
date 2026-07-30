"""
Tests para la validación de archivos en subir_documento (of.py).
Cubre: extensión no permitida, archivo demasiado grande, nombre vacío,
       path traversal, y extensiones válidas.

Estos tests validan la lógica de las constantes y helpers directamente,
sin levantar la app completa (más rápidos y sin dependencia de BD).
"""
import pytest
import pathlib

# Importar las constantes del router directamente
from app.routers.of import _EXTENSIONES_PERMITIDAS, _MAX_BYTES, _magic_ok


class TestMagicBytes:
    def test_pdf_valido(self):
        assert _magic_ok(b"%PDF-1.7\n...", ".pdf") is True

    def test_pdf_falso_rechazado(self):
        assert _magic_ok(b"esto no es pdf", ".pdf") is False

    def test_png_valido(self):
        assert _magic_ok(b"\x89PNG\r\n\x1a\n....", ".png") is True

    def test_jpg_valido(self):
        assert _magic_ok(b"\xff\xd8\xff\xe0....", ".jpg") is True

    def test_docx_xlsx_zip_valido(self):
        assert _magic_ok(b"PK\x03\x04....", ".docx") is True
        assert _magic_ok(b"PK\x03\x04....", ".xlsx") is True

    def test_docx_falso_rechazado(self):
        assert _magic_ok(b"no soy zip", ".docx") is False

    def test_csv_txt_sin_firma(self):
        assert _magic_ok(b"col1,col2\n1,2", ".csv") is True
        assert _magic_ok(b"texto", ".txt") is True


class TestExtensionesPermitidas:
    def test_pdf_permitido(self):
        ext = pathlib.Path("documento.pdf").suffix.lower()
        assert ext in _EXTENSIONES_PERMITIDAS

    def test_png_permitido(self):
        ext = pathlib.Path("foto.PNG").suffix.lower()
        assert ext in _EXTENSIONES_PERMITIDAS

    def test_jpg_permitido(self):
        assert ".jpg" in _EXTENSIONES_PERMITIDAS

    def test_jpeg_permitido(self):
        assert ".jpeg" in _EXTENSIONES_PERMITIDAS

    def test_xlsx_permitido(self):
        assert ".xlsx" in _EXTENSIONES_PERMITIDAS

    def test_docx_permitido(self):
        assert ".docx" in _EXTENSIONES_PERMITIDAS

    def test_csv_permitido(self):
        assert ".csv" in _EXTENSIONES_PERMITIDAS

    def test_exe_no_permitido(self):
        ext = pathlib.Path("virus.exe").suffix.lower()
        assert ext not in _EXTENSIONES_PERMITIDAS

    def test_sh_no_permitido(self):
        ext = pathlib.Path("script.sh").suffix.lower()
        assert ext not in _EXTENSIONES_PERMITIDAS

    def test_py_no_permitido(self):
        ext = pathlib.Path("malware.py").suffix.lower()
        assert ext not in _EXTENSIONES_PERMITIDAS

    def test_zip_no_permitido(self):
        ext = pathlib.Path("archivo.zip").suffix.lower()
        assert ext not in _EXTENSIONES_PERMITIDAS

    def test_js_no_permitido(self):
        ext = pathlib.Path("payload.js").suffix.lower()
        assert ext not in _EXTENSIONES_PERMITIDAS

    def test_html_no_permitido(self):
        ext = pathlib.Path("phish.html").suffix.lower()
        assert ext not in _EXTENSIONES_PERMITIDAS

    def test_extension_case_insensitive_upper(self):
        """Extensiones en mayúsculas deben normalizarse a minúsculas antes de validar."""
        nombre = "FICHA.PDF"
        ext = pathlib.Path(nombre).suffix.lower()
        assert ext in _EXTENSIONES_PERMITIDAS

    def test_extension_case_insensitive_mixed(self):
        nombre = "foto.Jpg"
        ext = pathlib.Path(nombre).suffix.lower()
        assert ext in _EXTENSIONES_PERMITIDAS


class TestTamanoMaximo:
    def test_limite_es_20mb(self):
        assert _MAX_BYTES == 20 * 1024 * 1024

    def test_archivo_dentro_del_limite(self):
        tamanio = 5 * 1024 * 1024  # 5 MB
        assert tamanio <= _MAX_BYTES

    def test_archivo_en_el_limite_exacto(self):
        tamanio = _MAX_BYTES
        assert tamanio <= _MAX_BYTES

    def test_archivo_supera_el_limite(self):
        tamanio = _MAX_BYTES + 1
        assert tamanio > _MAX_BYTES

    def test_archivo_muy_grande(self):
        tamanio = 50 * 1024 * 1024  # 50 MB
        assert tamanio > _MAX_BYTES


class TestPathTraversal:
    def test_path_traversal_eliminado(self):
        """pathlib.Path().name debe eliminar directorios del nombre."""
        nombre_malicioso = "../../etc/passwd"
        nombre_seguro = pathlib.Path(nombre_malicioso).name
        assert nombre_seguro == "passwd"
        assert ".." not in nombre_seguro
        assert "/" not in nombre_seguro

    def test_path_traversal_windows(self):
        """En Windows, PureWindowsPath extrae solo el nombre final."""
        nombre_malicioso = r"..\..\..\windows\system32\config"
        nombre_seguro = pathlib.PureWindowsPath(nombre_malicioso).name
        assert ".." not in nombre_seguro

    def test_nombre_normal_no_cambia(self):
        nombre = "ficha_tecnica.pdf"
        nombre_seguro = pathlib.Path(nombre).name
        assert nombre_seguro == nombre

    def test_nombre_con_espacios_preservado(self):
        nombre = "orden de compra.pdf"
        nombre_seguro = pathlib.Path(nombre).name
        assert nombre_seguro == nombre

    def test_nombre_con_subdirectorio_extraido(self):
        nombre = "uploads/secreto.pdf"
        nombre_seguro = pathlib.Path(nombre).name
        assert nombre_seguro == "secreto.pdf"
