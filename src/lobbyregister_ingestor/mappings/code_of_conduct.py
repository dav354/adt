"""Mapping helper for code of conduct."""

from __future__ import annotations

from typing import Any, Dict

from .common import scalar


def load_code_of_conduct(cur, entry_id: int, data: Dict[str, Any]) -> None:
    if not data:
        return
    cur.execute(
        "INSERT INTO public.code_of_conduct(entry_id, own_code_of_conduct, code_of_conduct_pdf_url) VALUES (%s,%s,%s)",
        (entry_id, data.get("ownCodeOfConduct"), scalar(data, "codeOfConductPdfUrl")),
    )
