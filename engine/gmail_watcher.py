import os
import uuid
from datetime import date

GMAIL_DEMO = os.getenv("GMAIL_DEMO_MODE", "true").lower() == "true"


def get_mock_invoices() -> list[dict]:
    """Return 3 hardcoded realistic Spanish invoice dicts for demo purposes."""
    today = date.today().isoformat()

    return [
        {
            "proveedor": "Amazon Web Services",
            "nif_proveedor": "W0184081H",
            "fecha": today,
            "numero_factura": "AWS-2025-00142",
            "base_imponible": 89.99,
            "tipo_iva": 21,
            "cuota_iva": 18.90,
            "total": 108.89,
            "concepto": "Servicios de hosting cloud EC2",
            "tipo_documento": "factura",
            "iva_label": "Tipo general",
            "iva_article": "Art. 90.Uno Ley 37/1992",
            "iva_confidence": "high",
            "exempt": False,
            "deducible": True,
            "porcentaje_deduccion": 100,
            "cuota_iva_deducible": 18.90,
            "deductibility_justification": "100% deducible — gasto profesional (hosting)",
            "deductibility_article": "Art. 28-30 Ley 35/2006 IRPF",
            "extraction_method": "mock",
            "parse_error": False,
            "origen": "gmail",
            "tipo": "gasto",
            "estado": "pendiente",
        },
        {
            "proveedor": "Renfe",
            "nif_proveedor": "A86868189",
            "fecha": today,
            "numero_factura": "RNF-2025-87431",
            "base_imponible": 45.00,
            "tipo_iva": 10,
            "cuota_iva": 4.50,
            "total": 49.50,
            "concepto": "Billete AVE Madrid-Barcelona viaje cliente",
            "tipo_documento": "ticket",
            "iva_label": "Tipo reducido",
            "iva_article": "Art. 91.Uno Ley 37/1992",
            "iva_confidence": "high",
            "exempt": False,
            "deducible": True,
            "porcentaje_deduccion": 100,
            "cuota_iva_deducible": 4.50,
            "deductibility_justification": "100% deducible — transporte profesional",
            "deductibility_article": "Art. 28-30 Ley 35/2006 IRPF",
            "extraction_method": "mock",
            "parse_error": False,
            "origen": "gmail",
            "tipo": "gasto",
            "estado": "pendiente",
        },
        {
            "proveedor": "Carrefour",
            "nif_proveedor": "A28425270",
            "fecha": today,
            "numero_factura": None,
            "base_imponible": 67.30,
            "tipo_iva": 21,
            "cuota_iva": 14.13,
            "total": 81.43,
            "concepto": "Compra supermercado alimentación personal",
            "tipo_documento": "ticket",
            "iva_label": "Tipo general",
            "iva_article": "Art. 90.Uno Ley 37/1992",
            "iva_confidence": "high",
            "exempt": False,
            "deducible": False,
            "porcentaje_deduccion": 0,
            "cuota_iva_deducible": 0.0,
            "deductibility_justification": "No deducible — gasto personal (supermercado)",
            "deductibility_article": "Art. 28 Ley 35/2006 IRPF — no deducible",
            "extraction_method": "mock",
            "parse_error": False,
            "origen": "gmail",
            "tipo": "gasto",
            "estado": "pendiente",
        },
    ]


def check_new_invoices(
    credentials_path: str = "",
    last_check_timestamp: str = "",
    user_profile: dict = None,
    tax_rules: dict = None,
    claude_client=None,
) -> list[dict]:
    """
    Scan Gmail for invoice attachments since last_check_timestamp.
    In demo mode, returns mock invoices.
    """
    if GMAIL_DEMO:
        return get_mock_invoices()

    # Real Gmail integration
    try:
        from simplegmail import Gmail

        gmail = Gmail(credentials_path)
        query = f"after:{last_check_timestamp} has:attachment"
        messages = gmail.get_messages(query=query)

        results = []
        allowed_extensions = (".pdf", ".jpg", ".png", ".jpeg", ".heic")

        for msg in messages:
            for attachment in msg.attachments:
                filename = attachment.filename.lower()
                if not any(filename.endswith(ext) for ext in allowed_extensions):
                    continue

                try:
                    from engine.invoice_parser import process_document

                    file_bytes = attachment.download()
                    file_type = "pdf" if filename.endswith(".pdf") else "image"
                    result = process_document(
                        file_bytes, file_type, user_profile, tax_rules, claude_client
                    )
                    result["origen"] = "gmail"
                    result["tipo"] = "gasto"
                    result["estado"] = "pendiente"
                    results.append(result)
                except Exception:
                    continue

        return results
    except Exception:
        return []
