import html
import re
from datetime import datetime
from urllib.parse import quote_plus, unquote, urljoin, urlparse, parse_qs
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)


def _clean_text(value):
    if not value:
        return ""
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def _trim(value, limit):
    value = _clean_text(value)
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + "..."


def _child_text(item, name):
    for child in item:
        tag = child.tag.split("}", 1)[-1].lower()
        if tag == name.lower():
            return child.text or ""
    return ""


def _rss_url(query, search_type):
    encoded_query = quote_plus(query)
    if search_type == "news":
        return f"https://news.google.com/rss/search?q={encoded_query}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
    return f"https://www.bing.com/search?q={encoded_query}&format=rss&setlang=zh-CN&cc=CN"


def _normalize_duckduckgo_link(link):
    link = html.unescape(link)
    if link.startswith("//"):
        link = "https:" + link
    parsed = urlparse(link)
    uddg = parse_qs(parsed.query).get("uddg")
    if uddg:
        return unquote(uddg[0])
    return link


def _web_search(query, max_results):
    url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10)
    response.raise_for_status()

    pattern = re.compile(
        r'<a[^>]+class="result__a"[^>]+href="(?P<link>[^"]+)"[^>]*>(?P<title>.*?)</a>',
        re.S,
    )
    snippet_pattern = re.compile(r'<a[^>]+class="result__snippet"[^>]*>(?P<snippet>.*?)</a>', re.S)
    snippets = [_clean_text(match.group("snippet")) for match in snippet_pattern.finditer(response.text)]

    items = []
    for index, match in enumerate(pattern.finditer(response.text)):
        if len(items) >= max_results:
            break
        items.append({
            "title": _clean_text(match.group("title")),
            "link": _normalize_duckduckgo_link(match.group("link")),
            "snippet": snippets[index] if index < len(snippets) else "",
            "published_at": "",
            "source": "DuckDuckGo",
        })
    return items


def _extract_table(table, max_rows=8, max_cols=6):
    caption = _clean_text(table.caption.get_text(" ", strip=True)) if table.caption else ""
    rows = []
    for row in table.find_all("tr")[:max_rows]:
        cells = row.find_all(["th", "td"])[:max_cols]
        values = [_clean_text(cell.get_text(" ", strip=True)) for cell in cells]
        if any(values):
            rows.append(values)
    return {"caption": caption, "rows": rows}


def _extract_images(soup, base_url, max_images=8):
    images = []
    for image in soup.find_all("img"):
        src = image.get("src") or image.get("data-src") or image.get("data-original")
        if not src or src.startswith("data:"):
            continue
        image_url = urljoin(base_url, src)
        alt = _clean_text(image.get("alt") or image.get("title") or "")
        if not alt and any(skip in image_url.lower() for skip in ["logo", "icon", "avatar", "sprite"]):
            continue
        images.append({
            "url": image_url,
            "alt": alt,
        })
        if len(images) >= max_images:
            break
    return images


def _extract_text_blocks(soup):
    for tag in soup(["script", "style", "noscript", "svg", "form", "nav", "footer", "header", "aside"]):
        tag.decompose()

    container = soup.find("article") or soup.find("main") or soup.body or soup
    blocks = []
    for tag in container.find_all(["h1", "h2", "h3", "p", "li"]):
        text = _clean_text(tag.get_text(" ", strip=True))
        if len(text) < 20 and tag.name not in {"h1", "h2", "h3"}:
            continue
        if text and (not blocks or blocks[-1] != text):
            blocks.append(text)
    return "\n".join(blocks)


def extract_page_content(url, timeout=12):
    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
            allow_redirects=True,
        )
        response.raise_for_status()
    except Exception as exc:
        return {
            "status": "error",
            "url": url,
            "final_url": url,
            "error": str(exc),
            "title": "",
            "text": "",
            "tables": [],
            "images": [],
        }

    content_type = response.headers.get("content-type", "")
    if "html" not in content_type.lower() and "xml" not in content_type.lower():
        return {
            "status": "skipped",
            "url": url,
            "final_url": response.url,
            "error": f"unsupported content-type: {content_type}",
            "title": "",
            "text": "",
            "tables": [],
            "images": [],
        }

    soup = BeautifulSoup(response.text, "html.parser")
    title = _clean_text(soup.title.get_text(" ", strip=True)) if soup.title else ""
    meta_description = ""
    description_tag = soup.find("meta", attrs={"name": "description"})
    if description_tag:
        meta_description = _clean_text(description_tag.get("content", ""))

    tables = [_extract_table(table) for table in soup.find_all("table")[:4]]
    images = _extract_images(soup, response.url)
    text = _extract_text_blocks(soup)
    if meta_description and meta_description not in text:
        text = meta_description + "\n" + text

    return {
        "status": "success",
        "url": url,
        "final_url": response.url,
        "title": title,
        "text": _trim(text, 6000),
        "tables": [table for table in tables if table["rows"]],
        "images": images,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }


def web_search(query, search_type="web", max_results=5):
    search_type = "news" if search_type == "news" else "web"
    max_results = max(1, min(int(max_results or 5), 10))

    try:
        if search_type == "web":
            items = _web_search(query, max_results)
            return {
                "status": "success",
                "query": query,
                "search_type": search_type,
                "results": items,
                "fetched_at": datetime.now().isoformat(timespec="seconds"),
            }

        response = requests.get(_rss_url(query, search_type), headers={"User-Agent": USER_AGENT}, timeout=10)
        response.raise_for_status()
        root = ElementTree.fromstring(response.content)
    except Exception as exc:
        return {
            "status": "error",
            "query": query,
            "search_type": search_type,
            "error": str(exc),
            "results": [],
            "fetched_at": datetime.now().isoformat(timespec="seconds"),
        }

    items = []
    for item in root.findall(".//item")[:max_results]:
        items.append({
            "title": _clean_text(_child_text(item, "title")),
            "link": _clean_text(_child_text(item, "link")),
            "snippet": _clean_text(_child_text(item, "description")),
            "published_at": _clean_text(_child_text(item, "pubDate")),
            "source": _clean_text(_child_text(item, "source")),
        })

    return {
        "status": "success",
        "query": query,
        "search_type": search_type,
        "results": items,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }


def web_research(query, search_type="news", max_results=5, max_pages=3):
    if search_type == "news":
        search = {
            "status": "success",
            "query": query,
            "search_type": "web",
            "results": _web_search(f"{query} 新闻 最新", max_results),
            "fetched_at": datetime.now().isoformat(timespec="seconds"),
        }
    else:
        search = web_search(query, search_type, max_results)
    pages = []
    if search.get("status") == "success":
        blocked_hosts = {"news.google.com", "www.google.com", "google.com", "duckduckgo.com", "www.duckduckgo.com"}
        for result in search.get("results", []):
            if len(pages) >= max_pages:
                break
            link = result.get("link")
            if not link:
                continue
            host = urlparse(link).netloc.lower()
            if host in blocked_hosts:
                continue
            page = extract_page_content(link)
            if page.get("status") == "success" and len(page.get("text", "")) < 120:
                continue
            page["search_title"] = result.get("title", "")
            page["search_snippet"] = result.get("snippet", "")
            page["search_source"] = result.get("source", "")
            pages.append(page)

    return {
        "status": search.get("status", "error"),
        "query": query,
        "search_type": search_type,
        "search_results": search.get("results", []),
        "pages": pages,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "error": search.get("error", ""),
    }
