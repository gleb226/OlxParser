from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, replace
from functools import lru_cache
from html import unescape
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


BASE_URL = "https://www.olx.ua/uk"
DEFAULT_LIMIT = 36

CATEGORY_PATHS = {
    "all": "list",
    "cars": "transport/legkovye-avtomobili",
    "phones": "elektronika/telefony-i-aksesuary/mobilnye-telefony-smartfony",
    "laptops": "elektronika/noutbuki-i-aksesuary/noutbuki",
    "tablets": "elektronika/telefony-i-aksesuary/planshety-el-knigi",
    "audio": "elektronika/audiotehnika",
    "games": "elektronika/igry-i-igrovye-pristavki",
    "appliances": "bytovaya-tehnika",
    "real_estate": "nedvizhimost/kvartiry",
    "house_garden": "dom-i-sad",
    "furniture": "dom-i-sad/mebel",
    "fashion": "moda-i-stil",
    "kids": "detskiy-mir",
    "sports": "hobbi-otdyh-i-sport/sport-otdyh",
    "jobs": "rabota",
}

CITY_SLUGS = {
    "all": "",
    "kyiv": "kiev",
    "kharkiv": "kharkov",
    "odesa": "odessa",
    "dnipro": "dnepr",
    "lviv": "lvov",
    "zaporizhzhia": "zaporozhe",
    "vinnytsia": "vinnitsa",
    "cherkasy": "cherkassy",
    "chernihiv": "chernigov",
    "chernivtsi": "chernovtsy",
    "ivano_frankivsk": "ivano-frankovsk",
    "kropyvnytskyi": "kirovograd",
    "lutsk": "lutsk",
    "mykolaiv": "nikolaev",
    "poltava": "poltava",
    "rivne": "rovno",
    "sumy": "sumy",
    "ternopil": "ternopol",
    "uzhhorod": "uzhgorod",
    "khmelnytskyi": "hmelnitskiy",
    "zhytomyr": "zhitomir",
}

CITY_NAMES = {
    "kyiv": ("київ", "киев", "kiev", "kyiv"),
    "kharkiv": ("харків", "харьков", "kharkiv", "kharkov"),
    "odesa": ("одеса", "одесса", "odesa", "odessa"),
    "dnipro": ("дніпро", "днепр", "dnipro", "dnepr"),
    "lviv": ("львів", "львов", "lviv", "lvov"),
    "zaporizhzhia": ("запоріжжя", "запорожье", "zaporizhzhia", "zaporozhe"),
    "vinnytsia": ("вінниця", "винница", "vinnytsia", "vinnitsa"),
    "cherkasy": ("черкаси", "черкассы", "cherkasy", "cherkassy"),
    "chernihiv": ("чернігів", "чернигов", "chernihiv", "chernigov"),
    "chernivtsi": ("чернівці", "черновцы", "chernivtsi", "chernovtsy"),
    "ivano_frankivsk": ("івано-франківськ", "ивано-франковск", "ivano-frankivsk", "ivano-frankovsk"),
    "kropyvnytskyi": ("кропивницький", "кировоград", "kropyvnytskyi", "kirovograd"),
    "lutsk": ("луцьк", "луцк", "lutsk"),
    "mykolaiv": ("миколаїв", "николаев", "mykolaiv", "nikolaev"),
    "poltava": ("полтава", "poltava"),
    "rivne": ("рівне", "ровно", "rivne", "rovno"),
    "sumy": ("суми", "сумы", "sumy"),
    "ternopil": ("тернопіль", "тернополь", "ternopil", "ternopol"),
    "uzhhorod": ("ужгород", "uzhhorod", "uzhgorod"),
    "khmelnytskyi": ("хмельницький", "хмельницкий", "khmelnytskyi", "hmelnitskiy"),
    "zhytomyr": ("житомир", "zhytomyr", "zhitomir"),
}

CITY_ALIASES = {
    token: slug
    for slug, tokens in CITY_NAMES.items()
    for token in tokens
}
CITY_ALIASES.update(
    {
        "біла церква": "belaya-tserkov",
        "белая церковь": "belaya-tserkov",
        "bila tserkva": "belaya-tserkov",
        "bila-tserkva": "belaya-tserkov",
        "кременчук": "kremenchug",
        "kremenchuk": "kremenchug",
        "мукачево": "mukachevo",
        "мукачеве": "mukachevo",
        "mukachevo": "mukachevo",
        "бровари": "brovary",
        "brovary": "brovary",
        "бориспіль": "borispol",
        "борисполь": "borispol",
        "boryspil": "borispol",
        "кам'янець-подільський": "kamenets-podolskiy",
        "камянець подільський": "kamenets-podolskiy",
        "каменец-подольский": "kamenets-podolskiy",
        "kolomyia": "kolomyya",
        "коломия": "kolomyya",
        "дрогобич": "drogobych",
        "drogobych": "drogobych",
        "ізмаїл": "izmail",
        "измаил": "izmail",
        "izmail": "izmail",
    }
)

STOP_WORDS_BY_CATEGORY = {
    "cars": (
        "чохол",
        "коврик",
        "килимок",
        "запчаст",
        "шина",
        "диск",
        "фара",
        "бампер",
        "розбор",
        "комплект",
        "магнітола",
        "акумулятор",
    ),
    "phones": (
        "чохол",
        "стекло",
        "скло",
        "кабель",
        "заряд",
        "навушник",
        "запчаст",
        "акумулятор",
        "корпус",
        "плівка",
    ),
    "laptops": (
        "заряд",
        "блок живлення",
        "чохол",
        "сумка",
        "клавіатура",
        "матриця",
        "запчаст",
    ),
}

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
    currency: str
    price_uah: int | None
    url: str
    image: str
    location: str
    date: str
    seller_type: str


def search_olx(
    query: str,
    min_price: int | None = None,
    max_price: int | None = None,
    sort: str = "asc",
    seller_type: str = "all",
    category: str = "all",
    city: str = "all",
    city_query: str = "",
    price_currency: str = "UAH",
    limit: int = DEFAULT_LIMIT,
) -> list[dict[str, str | int | None]]:
    if not query.strip():
        raise ValueError("Вкажіть назву для пошуку.")

    city_filter = _resolve_city(city, city_query)

    try:
        html = _download(_build_search_url(query.strip(), seller_type, category, city_filter["slug"]))
    except RuntimeError:
        if category == "all" and not city_filter["slug"]:
            raise
        try:
            html = _download(_build_search_url(query.strip(), seller_type, "all", city_filter["slug"]))
        except RuntimeError:
            html = _download(_build_search_url(query.strip(), seller_type, category, ""))

    listings = _extract_from_next_data(html) or _extract_fallback(html)
    listings = _enrich_listings(listings[: limit * 2])
    listings = _filter_by_category_url(listings, category)
    listings = _filter_by_relevance(listings, query, category)
    listings = _filter_by_city(listings, city_filter["tokens"])

    min_price_uah = _convert_to_uah(min_price, price_currency)
    max_price_uah = _convert_to_uah(max_price, price_currency)
    filtered = _filter_by_price(listings, min_price_uah, max_price_uah)
    
    filtered = _filter_by_seller_type(filtered, seller_type)

    reverse = sort == "desc"
    filtered.sort(key=lambda item: item.price_uah if item.price_uah is not None else 10**12, reverse=reverse)
    return [_format_listing(item, price_currency) for item in filtered[:limit]]


def parse_optional_price(value: str | None) -> int | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", "", value.strip())
    if cleaned in {"", "-"}:
        return None
    if not cleaned.isdigit():
        raise ValueError("Ціна має бути числом.")
    return int(cleaned)


def _download(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.6",
        },
    )
    try:
        with urlopen(request, timeout=16) as response:
            return response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        raise RuntimeError(f"Сервер OLX повернув помилку {exc.code}.") from exc
    except URLError as exc:
        raise RuntimeError("Не вдалося підключитися до OLX. Перевірте інтернет.") from exc


def _build_search_url(query: str, seller_type: str, category: str, city_slug: str) -> str:
    category_path = CATEGORY_PATHS.get(category, CATEGORY_PATHS["all"]).strip("/")
    city_slug = city_slug.strip("/")
    parts = [BASE_URL]
    if category == "all" and city_slug:
        parts.append(city_slug)
    else:
        parts.append(category_path)
        if city_slug:
            parts.append(city_slug)
    url = "/".join(part.strip("/") for part in parts) + f"/q-{_query_slug(query)}/"
    params = {}
    if seller_type in {"private", "business"}:
        params["search[private_business]"] = seller_type
    return f"{url}?{urlencode(params)}" if params else url


def _query_slug(query: str) -> str:
    return quote(re.sub(r"\s+", "-", query.strip().lower()))


def _resolve_city(city: str, city_query: str = "") -> dict[str, object]:
    custom = city_query.strip()
    if custom:
        normalized = custom.lower()
        slug = CITY_ALIASES.get(normalized) or _city_slug(custom)
        tokens = tuple({normalized, slug, *re.split(r"[\s,-]+", normalized)})
        return {"slug": slug, "tokens": tokens}

    if city == "all":
        return {"slug": "", "tokens": ()}

    slug = CITY_SLUGS.get(city, "")
    tokens = CITY_NAMES.get(city, ())
    return {"slug": slug, "tokens": tokens}


def _city_slug(value: str) -> str:
    translit = {
        "а": "a", "б": "b", "в": "v", "г": "g", "ґ": "g", "д": "d", "е": "e", "є": "e",
        "ж": "zh", "з": "z", "и": "i", "і": "i", "ї": "i", "й": "y", "к": "k", "л": "l",
        "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch", "ь": "", "ы": "y",
        "э": "e", "ю": "yu", "я": "ya", "ъ": "",
    }
    text = "".join(translit.get(char, char) for char in value.lower())
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text


def _enrich_listings(listings: list[Listing]) -> list[Listing]:
    if not listings:
        return []
    with ThreadPoolExecutor(max_workers=8) as executor:
        return list(executor.map(_enrich_listing, listings))


def _enrich_listing(listing: Listing) -> Listing:
    try:
        html = _download(listing.url)
    except RuntimeError:
        return listing

    detail = _detail_listing_from_next_data(html, listing.url)
    price_text = (detail.price_text if detail else "") or _detail_price(html) or listing.price_text
    price, currency = _parse_price(price_text)
    image = (detail.image if detail else "") or _detail_image(html) or listing.image
    seller_type = (detail.seller_type if detail else "") or _detail_seller_type(html) or listing.seller_type

    return Listing(
        title=listing.title,
        price_text=price_text,
        price=price,
        currency=currency,
        price_uah=_convert_to_uah(price, currency),
        url=listing.url,
        image=image,
        location=listing.location,
        date=listing.date,
        seller_type=seller_type,
    )


def _extract_from_next_data(html: str) -> list[Listing]:
    data = _next_data(html)
    if data is None:
        return []

    listings: list[Listing] = []
    seen: set[str] = set()
    for item in _walk_for_ads(data):
        title = str(item.get("title") or item.get("name") or "").strip()
        url = str(item.get("url") or item.get("href") or "").strip()
        if not title or not url:
            continue

        url = _absolute_url(url)
        clean_url = _clean_listing_url(url)
        if clean_url in seen:
            continue
        seen.add(clean_url)

        price_text = _pick_price_text(item)
        price, currency = _parse_price(price_text)
        listings.append(
            Listing(
                title=title,
                price_text=price_text,
                price=price,
                currency=currency,
                price_uah=_convert_to_uah(price, currency),
                url=clean_url,
                image=_pick_image(item),
                location=_pick_location(item),
                date=str(item.get("createdTime") or item.get("lastRefreshTime") or item.get("date") or "").strip(),
                seller_type=_pick_seller_type(item),
            )
        )
    return listings


def _detail_listing_from_next_data(html: str, url: str) -> Listing | None:
    clean_url = _clean_listing_url(url)
    for item in _extract_from_next_data(html):
        if _clean_listing_url(item.url) == clean_url:
            return item
    return None


def _next_data(html: str) -> object | None:
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
    if not match:
        return None
    try:
        return json.loads(unescape(match.group(1)))
    except json.JSONDecodeError:
        return None


def _walk_dicts(value: object) -> Iterable[dict]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


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
    candidates = (
        item.get("price"),
        item.get("displayPrice"),
        item.get("priceText"),
        item.get("formattedPrice"),
    )
    for candidate in candidates:
        value = _price_candidate_to_text(candidate)
        if value:
            return value
    return ""


def _price_candidate_to_text(candidate: object) -> str:
    if isinstance(candidate, dict):
        for key in ("displayValue", "value", "regularPrice", "convertedPrice", "label"):
            value = _price_candidate_to_text(candidate.get(key))
            if value:
                return value
    elif isinstance(candidate, (str, int, float)):
        return str(candidate).strip()
    return ""


def _pick_location(item: dict) -> str:
    candidates = (
        item.get("location"),
        item.get("cityName"),
        item.get("city"),
        item.get("regionName"),
    )
    for candidate in candidates:
        if isinstance(candidate, dict):
            text = " ".join(str(candidate.get(key) or "").strip() for key in ("name", "cityName", "regionName"))
            if text.strip():
                return re.sub(r"\s+", " ", text).strip()
        elif candidate:
            return str(candidate).strip()
    return ""


def _pick_image(item: dict) -> str:
    for key in ("photos", "images", "gallery", "image", "photo", "thumbnail", "photoLink", "imageUrl"):
        image = _first_image_url(item.get(key))
        if image:
            return image
    return _first_image_url(item)


def _first_image_url(value: object) -> str:
    if isinstance(value, str):
        for candidate in _image_candidates_from_text(value):
            if _looks_like_image_url(candidate):
                return _normalize_image_url(candidate)
        return ""

    if isinstance(value, list):
        for child in value:
            image = _first_image_url(child)
            if image:
                return image
        return ""

    if isinstance(value, dict):
        preferred_keys = (
            "link",
            "url",
            "src",
            "href",
            "original",
            "large",
            "medium",
            "small",
            "webp",
            "source",
        )
        for key in preferred_keys:
            image = _first_image_url(value.get(key))
            if image:
                return image
        for child in value.values():
            image = _first_image_url(child)
            if image:
                return image
    return ""


def _image_candidates_from_text(value: str) -> list[str]:
    cleaned = _normalize_escaped_url(value)
    candidates = [cleaned]
    candidates.extend(match.group(0) for match in re.finditer(r"https?:\/\/[^\s\"'<>,]+olxcdn\.com[^\s\"'<>,]+", cleaned))
    candidates.extend(match.group(0) for match in re.finditer(r"\/\/[^\s\"'<>,]+olxcdn\.com[^\s\"'<>,]+", cleaned))
    return candidates


def _normalize_escaped_url(value: str) -> str:
    cleaned = unescape(value).strip().strip('"').strip("'")
    cleaned = cleaned.replace("\\/", "/").replace("\\u002F", "/").replace("&amp;", "&")
    return cleaned


def _looks_like_image_url(value: str) -> bool:
    value = _normalize_escaped_url(value)
    return value.startswith(("http://", "https://", "//")) and "olxcdn.com" in value and not value.startswith("data:")


def _normalize_image_url(value: str) -> str:
    cleaned = _normalize_escaped_url(value)
    if cleaned.startswith("//"):
        cleaned = f"https:{cleaned}"
    return cleaned


def _pick_seller_type(item: dict) -> str:
    text = json.dumps(item, ensure_ascii=False).lower()
    explicit = str(
        item.get("private_business")
        or item.get("sellerType")
        or item.get("seller_type")
        or item.get("type")
        or ""
    ).lower()
    if explicit in {"private", "person", "owner"}:
        return "private"
    if explicit in {"business", "company", "professional", "dealer"}:
        return "business"
    if any(token in text for token in ("компанія", "бізнес", "дилер", "магазин", "фірма", "марка")):
        return "business"
    if any(token in text for token in ("приват", "власник")):
        return "private"
    return "unknown"


def _detail_price(html: str) -> str:
    data = _next_data(html)
    if data is not None:
        for item in _walk_dicts(data):
            price_text = _pick_price_text(item)
            if price_text and _price_to_int(price_text):
                return price_text

    clean = _strip_tags(html)
    patterns = (
        r"(?:\$|€)\s*\d[\d\s.,]{2,}",
        r"\d[\d\s.,]{2,}\s*(?:грн|₴|uah|usd|eur|\$|€|дол|євро|евро)",
        r'"price"\s*:\s*"?(\d{2,})',
    )
    for pattern in patterns:
        match = re.search(pattern, clean, re.I)
        if match:
            return match.group(0).strip()
    return ""


def _detail_image(html: str) -> str:
    data = _next_data(html)
    if data is not None:
        image = _first_image_url(data)
        if image:
            return image
    return _fallback_image(html)


def _detail_seller_type(html: str) -> str:
    clean = _strip_tags(html).lower()
    if any(token in clean for token in ("компанія", "бізнес", "магазин", "дилер", "фірма")):
        return "business"
    if any(token in clean for token in ("приват", "власник")):
        return "private"
    return ""


def _extract_fallback(html: str) -> list[Listing]:
    listings: list[Listing] = []
    seen: set[str] = set()
    matches = list(re.finditer(r'href="([^"]*/(?:d/uk/)?obyavlenie/[^"]+)"', html))

    for index, match in enumerate(matches):
        url = _clean_listing_url(_absolute_url(unescape(match.group(1))))
        if url in seen:
            continue

        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else match.end() + 5000
        block = html[start:end]
        title = _fallback_title(block)
        price_text = _fallback_price(block)
        if not title:
            continue

        seen.add(url)
        price, currency = _parse_price(price_text)
        listings.append(
            Listing(
                title=title,
                price_text=price_text,
                price=price,
                currency=currency,
                price_uah=_convert_to_uah(price, currency),
                url=url,
                image=_fallback_image(block),
                location=_fallback_location(block),
                date=_fallback_date(block),
                seller_type=_fallback_seller_type(block),
            )
        )
    return listings


def _fallback_title(block: str) -> str:
    for pattern in (r'alt="([^"]+)"', r"<h6[^>]*>(.*?)</h6>", r"<h4[^>]*>(.*?)</h4>", r"<h3[^>]*>(.*?)</h3>"):
        match = re.search(pattern, block, re.S)
        if match:
            text = _strip_tags(match.group(1))
            if text:
                return text
    return ""


def _fallback_price(block: str) -> str:
    clean = _strip_tags(block)
    match = re.search(
        r"(?:\$|€)\s*\d[\d\s.,]{2,}|\d[\d\s.,]{2,}\s*(?:грн|₴|uah|usd|eur|\$|€|дол|євро|евро)",
        clean,
        re.I,
    )
    return match.group(0).strip() if match else ""


def _fallback_image(block: str) -> str:
    for pattern in (
        r'<img[^>]+(?:src|data-src|data-original|srcset)="([^"]+)"',
        r'(https?:\\?/\\?/[^"\']+olxcdn\.com[^"\']+)',
        r'(//[^"\']+olxcdn\.com[^"\']+)',
    ):
        match = re.search(pattern, block)
        if match:
            image = _first_image_url(match.group(1))
            if image:
                return image
    return ""


def _fallback_location(block: str) -> str:
    clean = _strip_tags(block)
    for tokens in CITY_NAMES.values():
        for token in tokens:
            if token in clean.lower():
                return token.title()
    return ""


def _fallback_date(block: str) -> str:
    clean = _strip_tags(block)
    months = "січня|лютого|березня|квітня|травня|червня|липня|серпня|вересня|жовтня|листопада|грудня"
    match = re.search(rf"(сьогодні|вчора|\d{{1,2}}\s+(?:{months}))", clean, re.I)
    return match.group(1).strip() if match else ""


def _fallback_seller_type(block: str) -> str:
    clean = _strip_tags(block).lower()
    if any(token in clean for token in ("компанія", "бізнес", "дилер", "фірма")):
        return "business"
    if any(token in clean for token in ("приват", "власник")):
        return "private"
    return "unknown"


def _strip_tags(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _filter_by_category_url(listings: Iterable[Listing], category: str) -> list[Listing]:
    if category == "all":
        return list(listings)
    category_path = CATEGORY_PATHS.get(category)
    if not category_path:
        return list(listings)
    items = list(listings)
    filtered = [item for item in items if f"/{category_path}/" in item.url]
    return filtered or items


def _filter_by_price(listings: Iterable[Listing], min_price: int | None, max_price: int | None) -> list[Listing]:
    result: list[Listing] = []
    for item in listings:
        if item.price_uah is None:
            continue
        if min_price is not None and item.price_uah < min_price:
            continue
        if max_price is not None and item.price_uah > max_price:
            continue
        result.append(item)
    return result


def _filter_by_seller_type(listings: Iterable[Listing], seller_type: str) -> list[Listing]:
    if seller_type not in {"private", "business"}:
        return list(listings)
    items = list(listings)
    filtered: list[Listing] = []
    for item in items:
        if item.seller_type == seller_type:
            filtered.append(item)
        elif item.seller_type == "unknown":
            filtered.append(item)
    return filtered


def _filter_by_relevance(listings: Iterable[Listing], query: str, category: str) -> list[Listing]:
    query_words = _search_words(query)
    stop_words = STOP_WORDS_BY_CATEGORY.get(category, ())
    items = list(listings)
    result: list[Listing] = []

    for item in items:
        title = item.title.lower()
        if stop_words and any(word in title for word in stop_words):
            continue
        if query_words and not all(word in title for word in query_words[:2]):
            continue
        result.append(item)
    return result or items


def _filter_by_city(listings: Iterable[Listing], tokens: Iterable[str]) -> list[Listing]:
    tokens = tuple(token.lower() for token in tokens if token)
    if not tokens:
        return list(listings)
    items = list(listings)
    filtered = [item for item in items if any(token in item.location.lower() for token in tokens)]
    return filtered or items


def _search_words(query: str) -> list[str]:
    words = re.findall(r"[a-zA-Zа-яА-ЯіІїЇєЄґҐ0-9]+", query.lower())
    return [word for word in words if len(word) > 1]


def _format_listing(item: Listing, display_currency: str) -> dict[str, str | int | None]:
    payload = asdict(item)
    display_currency = display_currency if display_currency in {"UAH", "USD", "EUR"} else "UAH"
    display_amount = _convert_from_uah(item.price_uah, display_currency)
    payload["display_price_text"] = _format_money(display_amount, display_currency)
    payload["price_uah_text"] = _format_money(item.price_uah, "UAH")
    payload["original_price_text"] = _format_money(item.price, item.currency) if item.price else item.price_text
    payload["exchange_rate_text"] = _rate_text(item.currency)
    return payload


def _parse_price(price_text: str) -> tuple[int | None, str]:
    if not price_text:
        return None, "UAH"

    text = unescape(str(price_text)).replace("\xa0", " ").strip()
    lower = text.lower()
    currency = "UAH"
    if "$" in text or "usd" in lower or "дол" in lower:
        currency = "USD"
    elif "€" in text or "eur" in lower or "євро" in lower or "евро" in lower:
        currency = "EUR"

    number_match = re.search(r"\d[\d\s.,]*", text)
    if not number_match:
        return None, currency
    digits = re.sub(r"\D+", "", number_match.group(0))
    return (int(digits), currency) if digits else (None, currency)


def _price_to_int(price_text: str) -> int | None:
    amount, _ = _parse_price(price_text)
    return amount


def _convert_to_uah(amount: int | None, currency: str) -> int | None:
    if amount is None:
        return None
    currency = currency.upper()
    if currency == "UAH":
        return amount
    rate = _exchange_rates().get(currency)
    return round(amount * rate) if rate else amount


def _convert_from_uah(amount: int | None, currency: str) -> int | None:
    if amount is None:
        return None
    currency = currency.upper()
    if currency == "UAH":
        return amount
    rate = _exchange_rates().get(currency)
    return round(amount / rate) if rate else amount


def _rate_text(currency: str) -> str:
    currency = currency.upper()
    if currency == "UAH":
        return ""
    rate = _exchange_rates().get(currency)
    return f"1 {currency} = {_format_money(round(rate), 'UAH')}" if rate else ""


@lru_cache(maxsize=1)
def _exchange_rates() -> dict[str, float]:
    rates = {"USD": 41.5, "EUR": 45.0}
    rates.update(_privat_rates())
    if set(rates) < {"USD", "EUR"}:
        rates.update(_nbu_rates())
    return rates


def _privat_rates() -> dict[str, float]:
    url = "https://api.privatbank.ua/p24api/pubinfo?exchange&coursid=5"
    try:
        data = _json_url(url, timeout=8)
    except Exception:
        return {}

    rates: dict[str, float] = {}
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            code = str(item.get("ccy") or "").upper()
            if code in {"USD", "EUR"}:
                try:
                    rates[code] = float(item.get("sale") or item.get("buy"))
                except (TypeError, ValueError):
                    pass
    return rates


def _nbu_rates() -> dict[str, float]:
    url = "https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?json"
    try:
        data = _json_url(url, timeout=8)
    except Exception:
        return {}

    rates: dict[str, float] = {}
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            code = str(item.get("cc") or "").upper()
            if code in {"USD", "EUR"}:
                try:
                    rates[code] = float(item["rate"])
                except (KeyError, TypeError, ValueError):
                    pass
    return rates


def _json_url(url: str, timeout: int) -> object:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def _format_money(amount: int | None, currency: str) -> str:
    if amount is None:
        return "Ціну не вказано"
    value = f"{amount:,}".replace(",", " ")
    if currency == "USD":
        return f"${value}"
    if currency == "EUR":
        return f"€{value}"
    return f"{value} грн"


def _absolute_url(url: str) -> str:
    clean = _normalize_escaped_url(url)
    if clean.startswith("http"):
        return clean
    if clean.startswith("//"):
        return f"https:{clean}"
    return f"https://www.olx.ua{clean if clean.startswith('/') else '/' + clean}"


def _clean_listing_url(url: str) -> str:
    return url.split("?")[0]
