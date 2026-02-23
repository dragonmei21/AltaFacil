import json
from pathlib import Path

import pytest


ES_PATH = Path("i18n/es.json")
EN_PATH = Path("i18n/en.json")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _collect_keys(d: dict, prefix: str = "") -> set[str]:
    keys = set()
    for k, v in d.items():
        path = f"{prefix}.{k}" if prefix else k
        keys.add(path)
        if isinstance(v, dict):
            keys.update(_collect_keys(v, path))
    return keys


def _collect_empty_values(d: dict, prefix: str = "") -> list[str]:
    empty = []
    for k, v in d.items():
        path = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            empty.extend(_collect_empty_values(v, path))
        else:
            if isinstance(v, str) and v.strip() == "":
                # Spanish tooltips in tax_terms are intentionally blank by spec.
                if path.startswith("tax_terms.") and path.endswith("_tooltip"):
                    continue
                empty.append(path)
    return empty


def test_i18n_keys_match():
    es = _load(ES_PATH)
    en = _load(EN_PATH)

    es_keys = _collect_keys(es)
    en_keys = _collect_keys(en)

    missing_in_en = sorted(es_keys - en_keys)
    missing_in_es = sorted(en_keys - es_keys)

    report = []
    if missing_in_en:
        report.append("Missing in en.json:\n" + "\n".join(missing_in_en))
    if missing_in_es:
        report.append("Missing in es.json:\n" + "\n".join(missing_in_es))

    assert not report, "\n\n".join(report)


def test_es_no_empty_strings():
    es = _load(ES_PATH)
    empty = _collect_empty_values(es)
    assert not empty, "Empty Spanish strings:\n" + "\n".join(empty)


def test_tax_verdicts_present_in_both():
    es = _load(ES_PATH)
    en = _load(EN_PATH)

    assert "tax_verdicts" in es, "tax_verdicts missing in es.json"
    assert "tax_verdicts" in en, "tax_verdicts missing in en.json"

    es_keys = set(es["tax_verdicts"].keys())
    en_keys = set(en["tax_verdicts"].keys())

    assert es_keys == en_keys, (
        "tax_verdicts keys mismatch:\n"
        f"Missing in en.json: {sorted(es_keys - en_keys)}\n"
        f"Missing in es.json: {sorted(en_keys - es_keys)}"
    )
