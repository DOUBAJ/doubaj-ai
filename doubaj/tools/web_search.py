"""Optional web search. Default backend: DuckDuckGo HTML (no key). Optional: Tavily or Brave
(API key in settings) for better results. Results are injected into the prompt with numbered
sources so the model can cite them as [1], [2]..."""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urlparse

import httpx

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    content: str = ""


def _ddg(query: str, n: int) -> list[SearchResult]:
    from bs4 import BeautifulSoup
    r = httpx.post("https://html.duckduckgo.com/html/", data={"q": query}, headers={"User-Agent": UA},
                   timeout=15, follow_redirects=True)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    out = []
    for res in soup.select(".result"):
        a = res.select_one("a.result__a")
        if not a:
            continue
        href = a.get("href", "")
        if "uddg=" in href:
            href = unquote(parse_qs(urlparse(href).query).get("uddg", [href])[0])
        if "duckduckgo.com/y.js" in href:  # ads
            continue
        sn = res.select_one(".result__snippet")
        out.append(SearchResult(a.get_text(" ", strip=True), href, sn.get_text(" ", strip=True) if sn else ""))
        if len(out) >= n:
            break
    return out


def _tavily(query: str, n: int, key: str) -> list[SearchResult]:
    r = httpx.post("https://api.tavily.com/search", json={"api_key": key, "query": query, "max_results": n,
                                                           "include_raw_content": False}, timeout=20)
    r.raise_for_status()
    return [SearchResult(x.get("title", ""), x.get("url", ""), x.get("content", "")) for x in r.json().get("results", [])]


def _brave(query: str, n: int, key: str) -> list[SearchResult]:
    r = httpx.get("https://api.search.brave.com/res/v1/web/search", params={"q": query, "count": n},
                  headers={"X-Subscription-Token": key, "Accept": "application/json"}, timeout=15)
    r.raise_for_status()
    items = r.json().get("web", {}).get("results", [])
    return [SearchResult(x.get("title", ""), x.get("url", ""), re.sub("<[^>]+>", "", x.get("description", "")))
            for x in items]


def fetch_page_text(url: str, max_chars: int = 3500) -> str:
    from bs4 import BeautifulSoup
    try:
        r = httpx.get(url, headers={"User-Agent": UA}, timeout=10, follow_redirects=True)
        if "text/html" not in r.headers.get("content-type", ""):
            return ""
        soup = BeautifulSoup(r.text, "html.parser")
        for t in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            t.decompose()
        text = re.sub(r"\n{2,}", "\n", soup.get_text("\n", strip=True))
        return text[:max_chars]
    except Exception:
        return ""


def search(query: str, n: int = 6, backend: str = "duckduckgo", key: str = "", fetch_pages: int = 3) -> list[SearchResult]:
    if backend == "tavily" and key:
        results = _tavily(query, n, key)
    elif backend == "brave" and key:
        results = _brave(query, n, key)
    else:
        results = _ddg(query, n)
    for r in results[:fetch_pages]:
        r.content = fetch_page_text(r.url)
    return results


def format_for_prompt(query: str, results: list[SearchResult]) -> str:
    if not results:
        return f"[Web search for \"{query}\" returned no results.]"
    lines = [f"WEB SEARCH RESULTS for: \"{query}\" (cite sources as [n] with links)"]
    for i, r in enumerate(results, 1):
        lines.append(f"\n[{i}] {r.title}\nURL: {r.url}\nSnippet: {r.snippet}")
        if r.content:
            lines.append(f"Extract: {r.content}")
    return "\n".join(lines)
