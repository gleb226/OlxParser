from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from html import unescape
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen


BASE_URL = "https://www.olx.ua/uk/list/q-{}"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)


@dataclass
class Listing:
    title: str
    price_text: str
    price: int | None
    url: str
    image: str
    location: str
    date: str


def search_olx(
    query: str,
    min_price: int | None = None,
    max_price: int | None = None,
    sort: str = "asc",
    limit: int = 36,
) -> list[dict[str, str | int | None]]:
    if not query.strip():
        raise ValueError("Вкажи назву товару.")

    html = _download(BASE_URL.format(quote_plus(query.strip())))
    listings = _extract_from_next_data(html) or _extract_fallback(html)
    filtered = _filter_by_price(listings, min_price, max_price)
    reverse = sort == "desc"
    filtered.sort(key=lambda item: item.price if item.price is not None else 10**12, reverse=reverse)
    return [asdict(item) for item in filtered[:limit]]


def parse_optional_price(value: str | None) -> int | None:
    if value is None:
        return None
    cleaned = value.strip()
    if cleaned in {"", "-"}:
        return None
    if not cleaned.isdigit():
        raise ValueError("Ціна має бути числом або прочерком.")
    return int(cleaned)


def _download(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "uk-UA,uk;q=0.9"})
    try:
        with urlopen(request, timeout=16) as response:
            return response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        raise RuntimeError(f"OLX повернув помилку HTTP {exc.code}.") from exc
    except URLError as exc:
        raise RuntimeError("Не вдалося підключитися до OLX.") from exc


def _extract_from_next_data(html: str) -> list[Listing]:
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
    if not match:
        return []

    try:
        data = json.loads(unescape(match.group(1)))
    except json.JSONDecodeError:
        return []

    raw_items = list(_walk_for_ads(data))
    listings: list[Listing] = []
    seen: set[str] = set()

    for item in raw_items:
        title = str(item.get("title") or item.get("name") or "").strip()
        url = str(item.get("url") or item.get("href") or "").strip()
        if not title or not url:
            continue

        url = _absolute_url(url)
        if url in seen:
            continue
        seen.add(url)

        price_text = _pick_price_text(item)
        listings.append(
            Listing(
                title=title,
                price_text=price_text,
                price=_price_to_int(price_text),
                url=url,
                image=_pick_image(item),
                location=str(item.get("location") or item.get("cityName") or "").strip(),
                date=str(item.get("createdTime") or item.get("lastRefreshTime") or "").strip(),
            )
        )

    return listings


def _walk_for_ads(value: object) -> Iterable[dict]:
    if isinstance(value, dict):
        if _looks_like_ad(value):
            yield value
        for child in value.values():
            yield from _walk_for_ads(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_for_ads(child)


def _looks_like_ad(value: dict) -> bool:
    url = str(value.get("url") or value.get("href") or "")
    return bool(value.get("title") and ("/d/uk/obyavlenie/" in url or "/obyavlenie/" in url))


def _pick_price_text(item: dict) -> str:
    candidates = [
        item.get("price"),
        item.get("displayPrice"),
        item.get("priceText"),
        item.get("formattedPrice"),
    ]

    for candidate in candidates:
        if isinstance(candidate, dict):
            value = candidate.get("displayValue") or candidate.get("value") or candidate.get("regularPrice")
            if value:
                return str(value).strip()
        if candidate:
            return str(candidate).strip()

    return ""


def _pick_image(item: dict) -> str:
    photos = item.get("photos") or item.get("images")
    if isinstance(photos, list) and photos:
        first = photos[0]
        if isinstance(first, dict):
            return str(first.get("link") or first.get("url") or "").strip()
        return str(first).strip()
    return str(item.get("image") or item.get("photo") or "").strip()


def _extract_fallback(html: str) -> list[Listing]:
    listings: list[Listing] = []
    seen: set[str] = set()
    link_pattern = re.compile(r'href="([^"]*/d/uk/obyavlenie/[^"]+)"')
    matches = list(link_pattern.finditer(html))

    for index, match in enumerate(matches):
        url = _clean_listing_url(_absolute_url(unescape(match.group(1))))
        if url in seen:
            continue

        start = max(0, match.start() - 1800)
        end = matches[index + 1].start() if index + 1 < len(matches) else match.end() + 4200
        block = html[start:end]
        title = _fallback_title(block)
        price_text = _fallback_price(block)

        if not title:
            continue

        seen.add(url)
        listings.append(
            Listing(
                title=title,
                price_text=price_text,
                price=_price_to_int(price_text),
                url=url,
                image=_fallback_image(block),
                location=_fallback_location(block),
                date=_fallback_date(block),
            )
        )

    return listings


def _fallback_title(block: str) -> str:
    patterns = [
        r'alt="([^"]+)"',
        r"<h6[^>]*>(.*?)</h6>",
        r"<h4[^>]*>(.*?)</h4>",
    ]
    for pattern in patterns:
        match = re.search(pattern, block, re.S)
        if match:
            text = _strip_tags(match.group(1))
            if text:
                return text
    return ""


def _fallback_price(block: str) -> str:
    match = re.search(r"(\d[\d\s]*(?:грн|₴|\$|€))", _strip_tags(block), re.I)
    return match.group(1).strip() if match else ""


def _fallback_image(block: str) -> str:
    match = re.search(r'<img[^>]+src="([^"]+)"', block)
    if not match:
        return ""
    image = unescape(match.group(1)).strip()
    return image if image.startswith("http") else ""


def _fallback_location(block: str) -> str:
    return ""


def _fallback_date(block: str) -> str:
    clean = _strip_tags(block)
    months = "січня|лютого|березня|квітня|травня|червня|липня|серпня|вересня|жовтня|листопада|грудня"
    match = re.search(rf"(Сьогодні|Вчора|\d{{1,2}}\s+(?:{months}))", clean, re.I)
    return match.group(1).strip() if match else ""


def _strip_tags(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _filter_by_price(
    listings: Iterable[Listing], min_price: int | None, max_price: int | None
) -> list[Listing]:
    result: list[Listing] = []

    for item in listings:
        if item.price is None:
            continue
        if min_price is not None and item.price < min_price:
            continue
        if max_price is not None and item.price > max_price:
            continue
        result.append(item)

    return result


def _price_to_int(price_text: str) -> int | None:
    digits = re.sub(r"\D+", "", price_text)
    return int(digits) if digits else None


def _absolute_url(url: str) -> str:
    if url.startswith("http"):
        return url
    if url.startswith("//"):
        return f"https:{url}"
    return f"https://www.olx.ua{url if url.startswith('/') else '/' + url}"


def _clean_listing_url(url: str) -> str:
    return url.split("?")[0]
