"""Document processing service — PDF, DOCX, PPTX, TXT, and image extraction."""
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Tuple


def extract_text_from_pdf(file_path: str) -> Tuple[str, int]:
    """Extract text from PDF using PyMuPDF. Returns (text, page_count)."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(file_path)
        total_pages = len(doc)
        pages = []
        for page_num in range(total_pages):
            page = doc.load_page(page_num)
            text = page.get_text("text")
            if text and text.strip():
                pages.append(f"[Page {page_num + 1}]\n{text.strip()}")
            else:
                ocr_text = extract_text_from_image_bytes(page.get_pixmap().tobytes("png"))
                if ocr_text.strip():
                    pages.append(f"[Page {page_num + 1}]\n{ocr_text.strip()}")
        doc.close()
        return "\n\n".join(pages), total_pages
    except Exception as e:
        raise ValueError(f"PDF extraction failed: {str(e)}")


def extract_text_from_docx(file_path: str) -> Tuple[str, int]:
    """Extract text from DOCX using python-docx. Returns (text, estimated_pages)."""
    try:
        from docx import Document
        doc = Document(file_path)
        paragraphs = []
        for para in doc.paragraphs:
            if para.text.strip():
                paragraphs.append(para.text)
        # Also extract tables
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    paragraphs.append(row_text)
        full_text = "\n".join(paragraphs)
        # Estimate page count (approx 400 words per page)
        word_count = len(full_text.split())
        estimated_pages = max(1, word_count // 400)
        return full_text, estimated_pages
    except Exception as e:
        raise ValueError(f"DOCX extraction failed: {str(e)}")


def extract_text_from_doc(file_path: str) -> Tuple[str, int]:
    """Convert legacy Word files with LibreOffice, then extract the DOCX."""
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice and Path("C:/Program Files/LibreOffice/program/soffice.com").exists():
        soffice = "C:/Program Files/LibreOffice/program/soffice.com"
    if not soffice:
        raise ValueError(
            "Legacy .doc extraction requires LibreOffice. Install LibreOffice or save the file as .docx."
        )
    with tempfile.TemporaryDirectory() as output_dir:
        result = subprocess.run(
            [soffice, "--headless", "--convert-to", "docx", "--outdir", output_dir, file_path],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise ValueError(f"Legacy Word conversion failed: {result.stderr.strip()}")
        converted = Path(output_dir) / f"{Path(file_path).stem}.docx"
        if not converted.exists():
            raise ValueError("Legacy Word conversion did not produce a DOCX file.")
        return extract_text_from_docx(str(converted))


def extract_text_from_txt(file_path: str) -> Tuple[str, int]:
    """Extract text from plain TXT file."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        word_count = len(text.split())
        estimated_pages = max(1, word_count // 400)
        return text, estimated_pages
    except Exception as e:
        raise ValueError(f"TXT extraction failed: {str(e)}")


def extract_text_from_pptx(file_path: str) -> Tuple[str, int]:
    """Extract text from PowerPoint slides, including slide tables."""
    try:
        from pptx import Presentation

        presentation = Presentation(file_path)
        slides = []
        for slide_number, slide in enumerate(presentation.slides, start=1):
            parts = []
            for shape in slide.shapes:
                if not getattr(shape, "has_text_frame", False):
                    continue
                text = shape.text.strip()
                if text:
                    parts.append(text)
            if parts:
                slides.append(f"[Slide {slide_number}]\n" + "\n".join(parts))
        return "\n\n".join(slides), len(presentation.slides)
    except Exception as e:
        raise ValueError(f"PowerPoint extraction failed: {str(e)}")


def extract_text_from_ppt(file_path: str) -> Tuple[str, int]:
    """Convert legacy PowerPoint files with LibreOffice, then extract the PPTX."""
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice and Path("C:/Program Files/LibreOffice/program/soffice.com").exists():
        soffice = "C:/Program Files/LibreOffice/program/soffice.com"
    if not soffice:
        raise ValueError(
            "Legacy .ppt extraction requires LibreOffice. Install LibreOffice or save the file as .pptx."
        )
    with tempfile.TemporaryDirectory() as output_dir:
        result = subprocess.run(
            [soffice, "--headless", "--convert-to", "pptx", "--outdir", output_dir, file_path],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise ValueError(f"Legacy PowerPoint conversion failed: {result.stderr.strip()}")
        converted = Path(output_dir) / f"{Path(file_path).stem}.pptx"
        if not converted.exists():
            raise ValueError("Legacy PowerPoint conversion did not produce a PPTX file.")
        return extract_text_from_pptx(str(converted))


def extract_text_from_image_bytes(image_bytes: bytes) -> str:
    """Extract text from image bytes with the optional Tesseract OCR engine."""
    try:
        from PIL import Image, ImageOps, ImageFilter
        import pytesseract

        from io import BytesIO
        tesseract = shutil.which("tesseract")
        if not tesseract and Path("C:/Program Files/Tesseract-OCR/tesseract.exe").exists():
            tesseract = "C:/Program Files/Tesseract-OCR/tesseract.exe"
        if tesseract:
            pytesseract.pytesseract.tesseract_cmd = tesseract
        image = Image.open(BytesIO(image_bytes))
        image = ImageOps.exif_transpose(image).convert("L")
        image = ImageOps.autocontrast(image)
        if max(image.size) < 1600:
            scale = 1600 / max(image.size)
            image = image.resize(
                (round(image.width * scale), round(image.height * scale)),
                Image.Resampling.LANCZOS,
            )
        image = image.filter(ImageFilter.SHARPEN)
        text = pytesseract.image_to_string(image, config="--psm 6")
        return text.strip()
    except ImportError as e:
        raise ValueError(
            "OCR is unavailable. Install Pillow, pytesseract, and the Tesseract OCR engine."
        ) from e
    except Exception as e:
        raise ValueError(f"Image OCR failed: {str(e)}") from e


def extract_text_from_image(file_path: str) -> Tuple[str, int]:
    try:
        return extract_text_from_image_bytes(Path(file_path).read_bytes()), 1
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Image extraction failed: {str(e)}") from e


def extract_text(file_path: str, file_type: str) -> Tuple[str, int]:
    """Route to the appropriate extractor based on file type."""
    ext = file_type.lower().lstrip(".")
    if ext == "pdf":
        return extract_text_from_pdf(file_path)
    elif ext == "docx":
        return extract_text_from_docx(file_path)
    elif ext == "doc":
        return extract_text_from_doc(file_path)
    elif ext in ("pptx", "ppt"):
        if ext == "ppt":
            return extract_text_from_ppt(file_path)
        return extract_text_from_pptx(file_path)
    elif ext == "txt":
        return extract_text_from_txt(file_path)
    elif ext in ("png", "jpg", "jpeg", "webp", "bmp", "tiff", "tif"):
        return extract_text_from_image(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_type}")


def validate_document(file_path: str, max_size_mb: float = 25.0) -> None:
    """Validate document exists, is non-empty, and within size limit."""
    path = Path(file_path)
    if not path.exists():
        raise ValueError("File not found")
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > max_size_mb:
        raise ValueError(f"File size {size_mb:.1f}MB exceeds limit of {max_size_mb}MB")
    if path.stat().st_size == 0:
        raise ValueError("File is empty")


ALLOWED_EXTENSIONS = {
    "pdf", "docx", "doc", "pptx", "ppt", "txt",
    "png", "jpg", "jpeg", "webp", "bmp", "tiff", "tif",
}


def get_file_extension(filename: str) -> str:
    return Path(filename).suffix.lower().lstrip(".")


def is_allowed_file(filename: str) -> bool:
    return get_file_extension(filename) in ALLOWED_EXTENSIONS
