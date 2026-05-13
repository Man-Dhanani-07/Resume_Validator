import fitz  # PyMuPDF
import os
import pytesseract
from io import BytesIO
from PIL import Image
from PyPDF2 import PdfReader

def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract text from a PDF file page by page.

    Args:
        file_path: path to PDF document

    Returns:
        full extracted text as one string
    """

    # Open the PDF document
    doc = fitz.open(file_path)

    images = []
    raw_text = ""

    for pdf in doc:
        images.extend(convert_pdf_to_images(doc.write()))
        raw_text += pdf.get_text()                
                    
    # Extract text from images
    image_text = convert_images_to_text(images)
                    
    # Combine extracted text
    final_text = raw_text + "\n" + image_text
    return final_text

def convert_pdf_to_images(file_bytes, scale=2):
    images = []

    pdf = fitz.open(stream=file_bytes, filetype="pdf")

    for i, page in enumerate(pdf):
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))

        img_bytes = pix.tobytes("jpeg")

        images.append({i: img_bytes})

    return images

def convert_images_to_text(images):
    extracted_text = ""
    for img_dict in images:
        for _, img_bytes in img_dict.items():
            img = Image.open(BytesIO(img_bytes))
            try:
                osd = pytesseract.image_to_osd(img, output_type='dict')
                orientation = osd.get("orientation", 0)

                if orientation in [90, 180, 270]:
                    img = img.rotate(int(orientation), expand=True)

            except pytesseract.TesseractError:
                # If orientation detection fails, ignore and continue
                orientation = 0

            text = pytesseract.image_to_string(img)
            extracted_text += text + "\n\n"
    return extracted_text

def get_pdf_text(pdf_docs):
    text = ""
    for pdf in pdf_docs:
        pdf_reader = PdfReader(pdf)
        for page in pdf_reader.pages:
            text += page.extract_text()
    return text