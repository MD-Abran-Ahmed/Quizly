import os
import re
import fitz  # PyMuPDF

class PDFProcessingError(Exception):
    """Custom exception for PDF processing errors."""
    pass

def allowed_file(filename):
    """Check if the uploaded file has a PDF extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'pdf'

def clean_extracted_text(text: str) -> str:
    """
    Clean and normalize extracted text:
    - Replace consecutive whitespace with a single space
    - Normalize line breaks
    - Remove non-printable control characters
    """
    if not text:
        return ""
    # Normalize carriage returns
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # Remove control characters except newline and tab
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    # Remove excessive blank lines (more than 2)
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Strip leading/trailing whitespace
    return text.strip()

def extract_text_from_pdf(file_path: str) -> dict:
    """
    Extracts text and metadata from a PDF file using PyMuPDF.

    Returns:
        dict: {
            'text': str,
            'page_count': int,
            'word_count': int,
            'char_count': int,
            'is_scanned': bool
        }
    Raises:
        PDFProcessingError: on invalid file, corrupt document, or empty text.
    """
    if not os.path.exists(file_path):
        raise PDFProcessingError("The requested PDF file was not found on server.")

    # Validate file size
    file_size = os.path.getsize(file_path)
    if file_size == 0:
        raise PDFProcessingError("The uploaded PDF file is empty (0 bytes).")

    # Check PDF magic bytes
    try:
        with open(file_path, 'rb') as f:
            header = f.read(5)
            if not header.startswith(b'%PDF-'):
                raise PDFProcessingError("Invalid file format. The file is not a valid PDF document.")
    except Exception as e:
        if isinstance(e, PDFProcessingError):
            raise
        raise PDFProcessingError(f"Error reading file: {str(e)}")

    try:
        doc = fitz.open(file_path)
    except Exception as e:
        raise PDFProcessingError(f"Failed to parse PDF document. It may be password-protected or corrupt: {str(e)}")

    page_count = len(doc)
    if page_count == 0:
        doc.close()
        raise PDFProcessingError("The PDF document contains no pages.")

    extracted_pages = []
    total_images = 0

    for page_num in range(page_count):
        try:
            page = doc[page_num]
            page_text = page.get_text("text")
            if page_text:
                extracted_pages.append(page_text)
            total_images += len(page.get_images())
        except Exception:
            continue

    doc.close()

    raw_text = "\n\n".join(extracted_pages)
    cleaned_text = clean_extracted_text(raw_text)

    char_count = len(cleaned_text)
    word_count = len(cleaned_text.split())

    # Detect if document appears scanned / image-only with no OCR
    if char_count < 40:
        if total_images > 0:
            raise PDFProcessingError(
                "This appears to be a scanned or image-only PDF without an OCR text layer. "
                "Please upload a text-based PDF or run OCR before uploading."
            )
        else:
            raise PDFProcessingError(
                "No extractable text was found in this PDF document. "
                "Please ensure the document contains readable text notes."
            )

    return {
        'text': cleaned_text,
        'page_count': page_count,
        'word_count': word_count,
        'char_count': char_count,
        'is_scanned': False
    }

