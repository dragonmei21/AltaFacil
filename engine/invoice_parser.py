import json
import io
from pathlib import Path

import numpy as np
import pdfplumber
from PIL import Image
from openai import OpenAI

try:
    import cv2
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False

try:
    import pytesseract
    _TESSERACT_AVAILABLE = True
except ImportError:
    _TESSERACT_AVAILABLE = False

from engine.tax_rules import classify_iva, classify_deductibility


def preprocess_image(img: np.ndarray) -> np.ndarray:
    """
    Preprocess image for OCR. Apply in exact order:
    1. Convert to grayscale
    2. Denoise (h=10, templateWindowSize=7, searchWindowSize=21)
    3. Otsu threshold
    """
    if not _CV2_AVAILABLE:
        raise RuntimeError("opencv-python-headless is not installed")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)
    _, thresholded = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return thresholded


def extract_text_from_image(file_bytes: bytes) -> str:
    """
    Run OCR on image bytes.
    """
    if not _CV2_AVAILABLE or not _TESSERACT_AVAILABLE:
        raise RuntimeError("OCR libraries (opencv, pytesseract) are not available on this server")
    pil_img = Image.open(io.BytesIO(file_bytes))
    img_array = np.array(pil_img)

    # Convert RGBA to BGR if needed
    if len(img_array.shape) == 2:
        img_array = cv2.cvtColor(img_array, cv2.COLOR_GRAY2BGR)
    elif img_array.shape[2] == 4:
        img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
    elif img_array.shape[2] == 3:
        img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

    processed = preprocess_image(img_array)
    text = pytesseract.image_to_string(processed, lang="spa+eng", config="--psm 6")
    return text


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extract text from PDF.
    1. Try pdfplumber first.
    2. If extracted text < 50 chars: fall back to OCR per page.
    """
    text_parts = []

    # Try pdfplumber
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)

    full_text = "\n".join(text_parts)

    if len(full_text.strip()) >= 50:
        return full_text

    # Fallback: convert PDF pages to images and OCR each
    try:
        from pdf2image import convert_from_bytes

        images = convert_from_bytes(file_bytes)
        ocr_parts = []
        for pil_img in images:
            img_array = np.array(pil_img)
            img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            processed = preprocess_image(img_bgr)
            page_text = pytesseract.image_to_string(processed, lang="spa+eng", config="--psm 6")
            ocr_parts.append(page_text)
        return "\n".join(ocr_parts)
    except ImportError:
        return full_text


def parse_with_claude(raw_text: str, client: OpenAI) -> dict:
    """
    Send OCR text to OpenAI GPT for structured extraction.
    Temperature=0, max_tokens=500.
    Returns parsed dict or {"parse_error": True, "raw": response_text} on failure.
    """
    system_prompt = (
        "Eres un experto en facturas españolas. Extrae los campos solicitados "
        "con precisión. Devuelve SOLO JSON válido, sin texto adicional, "
        "sin backticks, sin explicaciones."
    )

    user_prompt = f"""Del siguiente texto de una factura española, extrae en JSON:
- proveedor (string): nombre del vendedor/empresa
- nif_proveedor (string|null): NIF o CIF del proveedor
- fecha (string): fecha en formato YYYY-MM-DD
- numero_factura (string|null): número de factura
- base_imponible (float): importe sin IVA
- tipo_iva (int): porcentaje de IVA (0, 4, 10, o 21)
- cuota_iva (float): importe del IVA
- total (float): importe total
- concepto (string): descripción breve del servicio o producto
- tipo_documento (string): 'factura', 'ticket', 'recibo', u 'otro'

Texto:
{raw_text}"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=500,
        temperature=0,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    response_text = response.choices[0].message.content

    try:
        parsed = json.loads(response_text)
        return parsed
    except json.JSONDecodeError as e:
        return {"parse_error": True, "raw": response_text, "error": str(e)}


def process_document(
    file_bytes: bytes,
    file_type: str,
    user_profile: dict,
    tax_rules: dict,
    claude_client: OpenAI,
) -> dict:
    """
    Master function — orchestrates full extraction + classification pipeline.

    Raises ValueError if OCR produces < 20 chars.
    """
    # Step 1: Extract text
    if file_type == "pdf":
        raw_text = extract_text_from_pdf(file_bytes)
        extraction_method = "pdfplumber"
    else:
        raw_text = extract_text_from_image(file_bytes)
        extraction_method = "tesseract"

    if len(raw_text.strip()) < 20:
        raise ValueError("OCR failed — image quality too low")

    # Step 2: Parse with Claude
    parsed = parse_with_claude(raw_text, claude_client)

    if parsed.get("parse_error"):
        return {
            "proveedor": "",
            "nif_proveedor": None,
            "fecha": "",
            "numero_factura": None,
            "base_imponible": 0.0,
            "tipo_iva": 21,
            "cuota_iva": 0.0,
            "total": 0.0,
            "concepto": "",
            "tipo_documento": "otro",
            "iva_label": "",
            "iva_article": "",
            "iva_confidence": "low",
            "exempt": False,
            "deducible": False,
            "porcentaje_deduccion": 0,
            "cuota_iva_deducible": 0.0,
            "deductibility_justification": "",
            "deductibility_article": "",
            "extraction_method": extraction_method,
            "parse_error": True,
            "raw_text": parsed.get("raw", ""),
        }

    # Step 3: Validate and recalculate cuota_iva
    base = float(parsed.get("base_imponible", 0))
    tipo_iva = int(parsed.get("tipo_iva", 21))
    extracted_cuota = float(parsed.get("cuota_iva", 0))
    calculated_cuota = round(base * tipo_iva / 100, 2)

    iva_discrepancy = abs(extracted_cuota - calculated_cuota) > 0.05
    cuota_iva = calculated_cuota  # Always use calculated

    total = round(base + cuota_iva, 2)

    # Step 4: Classify IVA rate via tax engine
    concepto = parsed.get("concepto", "")
    proveedor = parsed.get("proveedor", "")

    iva_result = classify_iva(concepto, proveedor, tax_rules)

    # Step 5: Classify deductibility
    ded_result = classify_deductibility(
        concepto,
        iva_result["tipo_iva"],
        iva_result["exempt"],
        user_profile,
        tax_rules,
    )

    # Compute actual cuota_iva_deducible
    ded_result["cuota_iva_deducible"] = round(
        cuota_iva * ded_result["porcentaje_deduccion"] / 100, 2
    )

    return {
        # From Claude extraction
        "proveedor": proveedor,
        "nif_proveedor": parsed.get("nif_proveedor"),
        "fecha": parsed.get("fecha", ""),
        "numero_factura": parsed.get("numero_factura"),
        "base_imponible": base,
        "tipo_iva": iva_result["tipo_iva"],
        "cuota_iva": cuota_iva,
        "total": total,
        "concepto": concepto,
        "tipo_documento": parsed.get("tipo_documento", "otro"),
        # From tax engine (classify_iva)
        "iva_label": iva_result["label"],
        "iva_article": iva_result["article"],
        "iva_confidence": iva_result["confidence"],
        "exempt": iva_result["exempt"],
        # From tax engine (classify_deductibility)
        "deducible": ded_result["deducible"],
        "porcentaje_deduccion": ded_result["porcentaje_deduccion"],
        "cuota_iva_deducible": ded_result["cuota_iva_deducible"],
        "deductibility_justification": ded_result["justification"],
        "deductibility_article": ded_result["article"],
        # Pipeline metadata
        "extraction_method": extraction_method,
        "parse_error": False,
        "iva_discrepancy": iva_discrepancy,
    }
