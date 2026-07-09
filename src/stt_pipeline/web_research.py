from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from stt_pipeline.additional_research import AdditionalResearchItem


@dataclass(frozen=True)
class WebResearchConfig:
    endpoint: str
    query_param: str = "q"
    limit: int = 5


class WebResearchHttpClient:
    def get_json(self, url: str) -> dict[str, Any]:
        request = Request(url, headers={"User-Agent": "stt-conference-web-research/0.1"})
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))


def build_web_research_url(
    endpoint: str,
    *,
    query: str,
    limit: int,
    query_param: str = "q",
) -> str:
    parts = urlsplit(endpoint)
    query_values = dict(parse_qsl(parts.query, keep_blank_values=True))
    query_values[query_param] = query
    query_values["limit"] = str(limit)
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query_values, quote_via=quote),
            parts.fragment,
        )
    )


def search_web_research(
    query: str,
    *,
    config: WebResearchConfig,
    http_client,
) -> tuple[AdditionalResearchItem, ...]:
    url = build_web_research_url(
        config.endpoint,
        query=query,
        limit=config.limit,
        query_param=config.query_param,
    )
    payload = http_client.get_json(url)
    return tuple(
        _item_from_result(query, raw_item)
        for raw_item in _raw_results(payload)[: config.limit]
        if _summary_from_raw(raw_item)
    )


def web_research_to_dict(
    items: tuple[AdditionalResearchItem, ...],
) -> dict[str, object]:
    return {"items": [asdict(item) for item in items]}


def _raw_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("items", "results", "organic"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    web_pages = payload.get("webPages")
    if isinstance(web_pages, dict) and isinstance(web_pages.get("value"), list):
        return [item for item in web_pages["value"] if isinstance(item, dict)]
    return []


def _item_from_result(query: str, raw_item: dict[str, Any]) -> AdditionalResearchItem:
    title = _clean(raw_item.get("title") or raw_item.get("name")) or query
    url = _clean(raw_item.get("url") or raw_item.get("link"))
    summary = _summary_from_raw(raw_item) or title
    evidence = url or f"web:{query}"
    return AdditionalResearchItem(
        source_path=f"web:{query}",
        title=title,
        summary=summary,
        url=url,
        evidence=evidence,
    )


def _summary_from_raw(raw_item: dict[str, Any]) -> str | None:
    return _clean(
        raw_item.get("summary")
        or raw_item.get("snippet")
        or raw_item.get("description")
        or raw_item.get("content")
    )


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).split())
    return cleaned or None
