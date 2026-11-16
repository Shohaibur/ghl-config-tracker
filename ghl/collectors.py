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


def get_pipelines(client: GHLClient) -> list[dict]:
    # Pipelines sorted by name. Stages keep GHL's own order, because that order matters.
    data = client.get("/opportunities/pipelines", params={"locationId": client.location_id})
    pipelines = data.get("pipelines") or []
    return sorted(pipelines, key=lambda p: ((p.get("name") or "").lower(), p.get("id") or ""))
