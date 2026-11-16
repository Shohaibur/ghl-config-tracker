"""One function per thing we read from GHL.

To add something new later (calendars, users...), add one function here.
Results are sorted so two snapshots line up cleanly when we diff them.
"""

from .client import GHLClient

# GHL calls the Company object "business"
MODELS = ("contact", "opportunity", "business")


def get_custom_fields(client: GHLClient, model: str) -> list[dict]:
    if model not in MODELS:
        raise ValueError(f"model must be one of {MODELS}, got {model!r}")
    data = client.get(f"/locations/{client.location_id}/customFields", params={"model": model})
    fields = data.get("customFields") or []
    return sorted(fields, key=lambda f: ((f.get("name") or "").lower(), f.get("id") or ""))


def get_companies(client: GHLClient) -> list[dict]:
    data = client.get("/businesses/", params={"locationId": client.location_id})
    companies = data.get("businesses") or []
    return sorted(companies, key=lambda c: ((c.get("name") or "").lower(), c.get("id") or ""))


def get_company_record(client: GHLClient, company_id: str) -> dict:
    """Full company record, including custom fields under "properties"."""
    data = client.get(f"/objects/business/records/{company_id}", params={"locationId": client.location_id})
    return data.get("record") or data


def get_opportunities(client: GHLClient) -> list[dict]:
    """All opportunities, page by page (100 per page)."""
    found, after, after_id = [], "", ""
    while True:
        params = {"location_id": client.location_id, "limit": 100}
        if after_id:
            params.update(startAfterId=after_id, startAfter=after)
        data = client.get("/opportunities/search", params=params)
        page = data.get("opportunities") or []
        found += page
        meta = data.get("meta") or {}
        after_id, after = meta.get("startAfterId"), meta.get("startAfter")
        if len(page) < 100 or not after_id:
            return found


def field_value(cf: dict):
    """GHL stores a custom field's value under different names depending on its type."""
    for key in ("fieldValue", "fieldValueString", "fieldValueNumber", "fieldValueArray", "value"):
        if cf.get(key) is not None:
            v = cf[key]
            return v.get("value") if isinstance(v, dict) and "value" in v else v
    return None


def get_pipelines(client: GHLClient) -> list[dict]:
    # Pipelines sorted by name. Stages keep GHL's own order, because that order matters.
    data = client.get("/opportunities/pipelines", params={"locationId": client.location_id})
    pipelines = data.get("pipelines") or []
    return sorted(pipelines, key=lambda p: ((p.get("name") or "").lower(), p.get("id") or ""))
