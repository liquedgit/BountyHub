import json
import re
from typing import Any

from app.ai.base import AIProvider, AIProviderError
from app.repositories.recon_asset import ReconAssetRepository
from app.schemas.triage import TriagedAsset

LABELS = {"likely_secret", "false_positive", "interesting", "routine"}

SYSTEM_PROMPT = (
    "You are a security triage assistant helping a bug-bounty hunter prioritise "
    "reconnaissance output from their own authorised engagements. For each asset "
    "give an integer score 0-100 (higher = more worth manual review) and a label: "
    "likely_secret (a real credential/token/key), false_positive (placeholder, "
    "example, test or hash-like noise), interesting (attack-surface worth a look), "
    "or routine. Reply with ONLY a JSON array of objects: "
    '{"id": <int>, "score": <int>, "label": <label>, "reason": <short string>}.'
)

_MAX_VALUE_LEN = 300


def redact(value: str, keep: int = 4) -> str:
    """Mask the middle of potentially sensitive strings before sending to an LLM."""
    if len(value) <= keep * 2 + 4:
        return value[:1] + "*" * (len(value) - 1) if value else value
    return f"{value[:keep]}…{value[-keep:]} (len={len(value)})"


def parse_triage_reply(text: str) -> list[dict[str, Any]]:
    """Extract the JSON array from a model reply, tolerating code fences/prose."""
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        raise AIProviderError("AI reply did not contain a JSON array")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        raise AIProviderError("AI reply was not valid JSON") from None
    if not isinstance(data, list):
        raise AIProviderError("AI reply was not a JSON array")
    return [d for d in data if isinstance(d, dict)]


class AITriageService:
    def __init__(self, provider: AIProvider, assets: ReconAssetRepository) -> None:
        self._provider = provider
        self._assets = assets

    @property
    def provider_name(self) -> str:
        return self._provider.name

    def triage(
        self, job_id: int | None = None, asset_ids: list[int] | None = None
    ) -> list[TriagedAsset]:
        assets = self._assets.list(job_id=job_id, asset_ids=asset_ids)
        if not assets:
            return []
        payload = [
            {
                "id": a.id,
                "type": a.asset_type,
                "value": (
                    redact(a.value)
                    if a.asset_type == "secret"
                    else a.value[:_MAX_VALUE_LEN]
                ),
                "metadata": _scrub_metadata(a.asset_metadata or {}),
            }
            for a in assets
        ]
        reply = self._provider.complete(SYSTEM_PROMPT, json.dumps(payload))
        by_id = {a.id: a for a in assets}
        results: dict[int, tuple[float, str, str]] = {}
        for item in parse_triage_reply(reply):
            asset = by_id.get(item.get("id")) if isinstance(item.get("id"), int) else None
            if asset is None:
                continue  # ignore ids the model invented
            try:
                score = max(0.0, min(100.0, float(item.get("score", 0))))
            except (TypeError, ValueError):
                score = 0.0
            label = item.get("label")
            if label not in LABELS:
                label = "routine"
            results[asset.id] = (score, label, str(item.get("reason", ""))[:500])
        self._assets.save_triage(results)
        ranked = sorted(results.items(), key=lambda kv: kv[1][0], reverse=True)
        return [
            TriagedAsset(
                id=i,
                asset_type=by_id[i].asset_type,
                value=by_id[i].value,
                score=s,
                label=lbl,
                reason=r,
            )
            for i, (s, lbl, r) in ranked
        ]


def _scrub_metadata(meta: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in meta.items():
        if re.search(r"secret|token|key|password|value", k, re.I) and isinstance(v, str):
            out[k] = redact(v)
        else:
            out[k] = v
    return out
