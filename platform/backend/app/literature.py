"""Real literature metadata providers with explicit, source-level provenance."""
import html
import json
import re
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.core.config import get_settings


@dataclass(frozen=True)
class RetrievedPaper:
    source: str
    external_id: str
    title: str
    authors: list[str]
    publication_year: int | None
    abstract: str | None
    url: str | None
    doi: str | None
    cited_by_count: int
    raw_metadata: dict[str, Any]


def _get_json(base_url: str, params: dict[str, str | int]) -> dict:
    settings = get_settings()
    request = Request(f"{base_url}?{urlencode(params)}", headers={"Accept": "application/json", "User-Agent": "AsterPlatform/0.2"})
    with urlopen(request, timeout=settings.literature_timeout_seconds) as response:  # nosec B310 - fixed HTTPS providers
        return json.loads(response.read().decode("utf-8"))


def _plain_text(value: str | None) -> str | None:
    if not value:
        return None
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(value))).strip() or None


def _openalex_abstract(index: dict[str, list[int]] | None) -> str | None:
    if not index:
        return None
    words = [(position, word) for word, positions in index.items() for position in positions]
    return " ".join(word for _, word in sorted(words)) or None


def search_crossref(question: str, limit: int = 20) -> list[RetrievedPaper]:
    settings = get_settings()
    params: dict[str, str | int] = {"query.bibliographic": question, "rows": min(max(limit, 1), 100), "select": "DOI,title,author,published,abstract,URL,is-referenced-by-count,type"}
    if settings.crossref_mailto:
        params["mailto"] = settings.crossref_mailto
    payload = _get_json("https://api.crossref.org/works", params)
    papers: list[RetrievedPaper] = []
    for item in payload.get("message", {}).get("items", []):
        doi = item.get("DOI")
        title = next(iter(item.get("title", [])), "Untitled work")
        date_parts = item.get("published", {}).get("date-parts", [[]])
        year = date_parts[0][0] if date_parts and date_parts[0] else None
        authors = [" ".join(part for part in (author.get("given"), author.get("family")) if part) for author in item.get("author", [])]
        papers.append(RetrievedPaper("crossref", doi or item.get("URL", title), title, authors, year, _plain_text(item.get("abstract")), item.get("URL"), doi, int(item.get("is-referenced-by-count") or 0), {"type": item.get("type")}))
    return papers


def search_openalex(question: str, limit: int = 20) -> list[RetrievedPaper]:
    settings = get_settings()
    if not settings.openalex_api_key:
        return []
    payload = _get_json("https://api.openalex.org/works", {"search": question, "per-page": min(max(limit, 1), 100), "api_key": settings.openalex_api_key})
    papers: list[RetrievedPaper] = []
    for item in payload.get("results", []):
        authors = [authorship.get("author", {}).get("display_name", "Unknown") for authorship in item.get("authorships", [])]
        papers.append(RetrievedPaper("openalex", item["id"], item.get("display_name") or "Untitled work", authors, item.get("publication_year"), _openalex_abstract(item.get("abstract_inverted_index")), item.get("doi") or item.get("id"), item.get("doi"), int(item.get("cited_by_count") or 0), {"type": item.get("type"), "is_retracted": item.get("is_retracted", False)}))
    return papers


def retrieve_literature(question: str, limit: int = 20) -> list[RetrievedPaper]:
    """Return deduplicated real metadata. OpenAlex enriches Crossref when configured."""
    candidates = search_openalex(question, limit) + search_crossref(question, limit)
    unique: dict[str, RetrievedPaper] = {}
    for paper in candidates:
        key = (paper.doi or paper.title).strip().lower()
        current = unique.get(key)
        if current is None or (paper.abstract and not current.abstract):
            unique[key] = paper
    return list(unique.values())


def serialize_paper(paper: RetrievedPaper) -> dict[str, Any]:
    return asdict(paper)
