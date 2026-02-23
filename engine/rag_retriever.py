"""RAG retriever for El Gestor chatbot.

Architecture:
- Vector store : ChromaDB (local, persisted to data/chroma/)
- Embeddings   : OpenAI text-embedding-3-small
- Collections  :
    'ledger_entries' — one document per ledger row, upserted by UUID
    'tax_rules'      — one document per rule category, fixed IDs (idempotent)
- Index sync   :
    Startup (chatbot page): full re-index via index_ledger() + index_tax_rules()
    After save_to_ledger() in Scanner: single-entry upsert via index_entry()

All public functions degrade gracefully — if ChromaDB or the API key is
unavailable, they return False/empty-string instead of raising.
"""

import os
from pathlib import Path

import pandas as pd

CHROMA_PATH = Path(__file__).parent.parent / "data" / "chroma"


# ---------------------------------------------------------------------------
# Internal helpers — client and embedding function
# ---------------------------------------------------------------------------

def _get_client():
    """Return a ChromaDB PersistentClient, or None if chromadb is not installed."""
    try:
        import chromadb  # noqa: F401 — optional dependency
        CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        return chromadb.PersistentClient(path=str(CHROMA_PATH))
    except Exception:
        return None


def _get_ef():
    """Return an OpenAI embedding function, or None if key/package missing."""
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return None
    try:
        from chromadb.utils import embedding_functions
        return embedding_functions.OpenAIEmbeddingFunction(
            api_key=api_key,
            model_name="text-embedding-3-small",
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Serialisation — rows and rules to plain text
# ---------------------------------------------------------------------------

def _row_to_text(row: dict) -> str:
    """
    Serialise a ledger row to a natural-language string for embedding.

    Example output:
        GASTO | 2025-03-15 | AWS | Hosting EC2 |
        Base: €89.99 | IVA 21% (€18.90) | Total: €108.89 |
        100% deducible (€18.90 IVA deducible) |
        Art. 28-30 Ley 35/2006 IRPF | 2025-Q1 | Estado: pendiente
    """
    tipo = row.get("tipo", "")
    fecha = row.get("fecha", "")
    proveedor = row.get("proveedor_cliente", "")
    concepto = row.get("concepto", "")
    base = float(row.get("base_imponible", 0) or 0)
    iva_pct = row.get("tipo_iva", 0)
    iva_cuota = float(row.get("cuota_iva", 0) or 0)
    total = float(row.get("total", 0) or 0)
    ded_pct = int(row.get("porcentaje_deduccion", 0) or 0)
    ded_cuota = float(row.get("cuota_iva_deducible", 0) or 0)
    aeat = row.get("aeat_articulo", "")
    trimestre = row.get("trimestre", "")
    estado = row.get("estado", "")

    deducible_text = (
        f"{ded_pct}% deducible (€{ded_cuota:.2f} IVA deducible)"
        if ded_pct > 0
        else "no deducible"
    )

    return (
        f"{tipo.upper()} | {fecha} | {proveedor} | {concepto} | "
        f"Base: €{base:.2f} | IVA {iva_pct}% (€{iva_cuota:.2f}) | Total: €{total:.2f} | "
        f"{deducible_text} | {aeat} | {trimestre} | Estado: {estado}"
    )


def _rule_to_text(category: str, rule_data: dict, rule_type: str) -> str:
    """Serialise a tax rule entry to a natural-language string for embedding."""
    keywords = ", ".join(rule_data.get("keywords", []))
    article = rule_data.get("article", "")

    if rule_type == "iva":
        label = rule_data.get("label", "")
        return (
            f"IVA {category}% ({label}): aplica a {keywords}. "
            f"Artículo: {article}."
        )
    else:
        pct = rule_data.get("pct", 100)
        condition = rule_data.get("condition", "")
        cond_text = f" Condición: {condition}." if condition else ""
        return (
            f"Deducibilidad {category} ({pct}%): aplica a {keywords}.{cond_text} "
            f"Artículo: {article}."
        )


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------

def index_ledger(df: pd.DataFrame) -> bool:
    """
    (Re-)index all ledger rows into the 'ledger_entries' collection.

    Uses upsert — safe to call multiple times, no duplicates.
    Skips rows without an id.
    Returns True on success, False on any failure (app continues without RAG).
    """
    client = _get_client()
    ef = _get_ef()
    if client is None or ef is None or df.empty:
        return False

    try:
        collection = client.get_or_create_collection(
            name="ledger_entries",
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )

        documents, ids, metadatas = [], [], []
        for _, row in df.iterrows():
            row_dict = row.to_dict()
            entry_id = str(row_dict.get("id", "")).strip()
            if not entry_id:
                continue
            documents.append(_row_to_text(row_dict))
            ids.append(entry_id)
            metadatas.append({
                "tipo": str(row_dict.get("tipo", "")),
                "trimestre": str(row_dict.get("trimestre", "")),
                "deducible": str(row_dict.get("deducible", "")),
                "fecha": str(row_dict.get("fecha", "")),
            })

        if documents:
            collection.upsert(documents=documents, ids=ids, metadatas=metadatas)
        return True

    except Exception:
        return False


def index_entry(entry: dict) -> bool:
    """
    Upsert a single ledger entry into the vector store.

    Called immediately after save_to_ledger() so the new entry is
    searchable in the chatbot without a full re-index.
    entry must have an 'id' key (set by save_to_ledger).
    Returns True on success.
    """
    entry_id = str(entry.get("id", "")).strip()
    if not entry_id:
        return False

    client = _get_client()
    ef = _get_ef()
    if client is None or ef is None:
        return False

    try:
        collection = client.get_or_create_collection(
            name="ledger_entries",
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )
        collection.upsert(
            documents=[_row_to_text(entry)],
            ids=[entry_id],
            metadatas=[{
                "tipo": str(entry.get("tipo", "")),
                "trimestre": str(entry.get("trimestre", "")),
                "deducible": str(entry.get("deducible", "")),
                "fecha": str(entry.get("fecha", "")),
            }],
        )
        return True

    except Exception:
        return False


def index_tax_rules(rules: dict) -> bool:
    """
    Index all tax rules into the 'tax_rules' collection.

    Uses fixed, deterministic IDs (e.g. 'iva_21', 'ded_partial_50') so
    calling this multiple times is idempotent via upsert.
    Returns True on success.
    """
    client = _get_client()
    ef = _get_ef()
    if client is None or ef is None:
        return False

    try:
        collection = client.get_or_create_collection(
            name="tax_rules",
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )

        documents, ids = [], []

        for rate, rule_data in rules.get("iva_rates", {}).items():
            documents.append(_rule_to_text(rate, rule_data, "iva"))
            ids.append(f"iva_{rate}")

        for category, rule_data in rules.get("deductibility_rules", {}).items():
            documents.append(_rule_to_text(category, rule_data, "deductibility"))
            ids.append(f"ded_{category}")

        if documents:
            collection.upsert(documents=documents, ids=ids)
        return True

    except Exception:
        return False


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def retrieve_context(query: str, k_ledger: int = 5, k_rules: int = 3) -> str:
    """
    Retrieve semantically relevant ledger entries and tax rules for a query.

    Returns a formatted string ready to inject into the system prompt.
    Returns an empty string on any failure — the chatbot degrades gracefully
    to aggregate-summary-only mode rather than crashing.

    Args:
        query     : The user's message to embed and search against.
        k_ledger  : Max ledger entries to retrieve (capped by collection size).
        k_rules   : Max tax rules to retrieve (capped by collection size).
    """
    client = _get_client()
    ef = _get_ef()
    if client is None or ef is None:
        return ""

    ledger_docs: list[str] = []
    rules_docs: list[str] = []

    try:
        ledger_col = client.get_collection(
            name="ledger_entries", embedding_function=ef
        )
        count = ledger_col.count()
        if count > 0:
            results = ledger_col.query(
                query_texts=[query], n_results=min(k_ledger, count)
            )
            ledger_docs = results.get("documents", [[]])[0]
    except Exception:
        pass

    try:
        rules_col = client.get_collection(
            name="tax_rules", embedding_function=ef
        )
        count = rules_col.count()
        if count > 0:
            results = rules_col.query(
                query_texts=[query], n_results=min(k_rules, count)
            )
            rules_docs = results.get("documents", [[]])[0]
    except Exception:
        pass

    if not ledger_docs and not rules_docs:
        return ""

    parts: list[str] = []

    if ledger_docs:
        parts.append(
            "ENTRADAS RELEVANTES DEL LIBRO DE CUENTAS (búsqueda semántica):"
        )
        for doc in ledger_docs:
            parts.append(f"  • {doc}")

    if rules_docs:
        if parts:
            parts.append("")
        parts.append("REGLAS FISCALES RELEVANTES:")
        for doc in rules_docs:
            parts.append(f"  • {doc}")

    return "\n".join(parts)
