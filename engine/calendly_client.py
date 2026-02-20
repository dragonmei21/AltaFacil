import os
import uuid
import requests
from datetime import datetime, timedelta, date

CALENDLY_BASE = "https://api.calendly.com"
CALENDLY_DEMO = os.getenv("CALENDLY_DEMO_MODE", "true").lower() == "true"


def get_mock_events() -> list[dict]:
    """Return 4 hardcoded Calendly event dicts for demo purposes."""
    today = date.today()

    return [
        {
            "event_uuid": str(uuid.uuid4()),
            "nombre_evento": "Consultoría de estrategia",
            "cliente_nombre": "Ana García",
            "cliente_email": "ana.garcia@ejemplo.com",
            "fecha_inicio": (today - timedelta(days=5)).isoformat() + "T10:00:00Z",
            "fecha_fin": (today - timedelta(days=5)).isoformat() + "T11:00:00Z",
            "estado": "completado",
            "precio": 150.00,
        },
        {
            "event_uuid": str(uuid.uuid4()),
            "nombre_evento": "Auditoría UX",
            "cliente_nombre": "Tech Startup SL",
            "cliente_email": "info@techstartup.es",
            "fecha_inicio": (today - timedelta(days=2)).isoformat() + "T14:00:00Z",
            "fecha_fin": (today - timedelta(days=2)).isoformat() + "T16:00:00Z",
            "estado": "completado",
            "precio": 400.00,
        },
        {
            "event_uuid": str(uuid.uuid4()),
            "nombre_evento": "Llamada de seguimiento",
            "cliente_nombre": "Pedro López",
            "cliente_email": "pedro.lopez@correo.com",
            "fecha_inicio": (today + timedelta(days=3)).isoformat() + "T09:00:00Z",
            "fecha_fin": (today + timedelta(days=3)).isoformat() + "T09:30:00Z",
            "estado": "activo",
            "precio": None,
        },
        {
            "event_uuid": str(uuid.uuid4()),
            "nombre_evento": "Discovery call",
            "cliente_nombre": "María Fernández",
            "cliente_email": "maria.fernandez@email.com",
            "fecha_inicio": (today - timedelta(days=7)).isoformat() + "T16:00:00Z",
            "fecha_fin": (today - timedelta(days=7)).isoformat() + "T16:30:00Z",
            "estado": "completado",
            "precio": 0.0,
        },
    ]


def get_user_uri(token: str) -> str:
    """GET /users/me -> return user URI string."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp = requests.get(f"{CALENDLY_BASE}/users/me", headers=headers)
    resp.raise_for_status()
    return resp.json()["resource"]["uri"]


def get_scheduled_events(
    token: str, user_uri: str = "", min_start_time: str = None
) -> list[dict]:
    """
    Get scheduled events from Calendly.
    In demo mode, returns mock events.
    """
    if CALENDLY_DEMO:
        return get_mock_events()

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    params = {"user": user_uri, "status": "active"}
    if min_start_time:
        params["min_start_time"] = min_start_time

    resp = requests.get(f"{CALENDLY_BASE}/scheduled_events", headers=headers, params=params)
    resp.raise_for_status()

    events = []
    for item in resp.json().get("collection", []):
        # Get invitee info
        event_uri = item["uri"]
        inv_resp = requests.get(f"{event_uri}/invitees", headers=headers)
        invitees = inv_resp.json().get("collection", []) if inv_resp.ok else []
        invitee = invitees[0] if invitees else {}

        status_map = {"active": "activo", "completed": "completado", "canceled": "cancelado"}

        events.append({
            "event_uuid": item["uri"].split("/")[-1],
            "nombre_evento": item.get("name", ""),
            "cliente_nombre": invitee.get("name", ""),
            "cliente_email": invitee.get("email", ""),
            "fecha_inicio": item.get("start_time", ""),
            "fecha_fin": item.get("end_time", ""),
            "estado": status_map.get(item.get("status", ""), item.get("status", "")),
            "precio": None,
        })

    return events


def generate_invoice_draft(event: dict, user_profile: dict) -> dict:
    """
    Convert a Calendly event into a ledger-ready ingreso draft.
    """
    base = event.get("precio") or 0.0
    tipo_iva = 21
    cuota_iva = round(base * tipo_iva / 100, 2)

    return {
        "fecha": event["fecha_inicio"][:10],
        "tipo": "ingreso",
        "proveedor_cliente": event.get("cliente_nombre", ""),
        "nif": "",
        "concepto": event.get("nombre_evento", ""),
        "numero_factura": "",
        "base_imponible": base,
        "tipo_iva": tipo_iva,
        "cuota_iva": cuota_iva,
        "total": round(base + cuota_iva, 2),
        "deducible": False,
        "porcentaje_deduccion": 0,
        "cuota_iva_deducible": 0.0,
        "aeat_articulo": "Art. 90.Uno Ley 37/1992",
        "estado": "pendiente",
        "origen": "calendly",
    }
