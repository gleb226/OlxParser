import asyncio
import httpx
import json
import re
import random
from dataclasses import asdict, dataclass, replace
from functools import lru_cache
from html import unescape
from typing import Iterable
from urllib.parse import quote, urlencode

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
        "чохол", "коврик", "килимок", "запчаст", "шина", "диск", "фара", "бампер", "розбор", "комплект", "магнітола", "акумулятор",
    ),
    "phones": (
        "чохол", "стекло", "скло", "кабель", "заряд", "навушник", "запчаст", "акумулятор", "корпус", "плівка",
    ),
    "laptops": (
        "заряд", "блок живлення", "чохол", "сумка", "клавіатура", "матриця", "запчаст",
    ),
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
]

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
    description: str = ""
    parameters: list[dict[str, str]] = None

async def search_olx(
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

    async with httpx.AsyncClient(timeout=18, follow_redirects=True) as client:
        try:
            html = await _download(client, _build_search_url(query.strip(), seller_type, category, city_filter["slug"]))
        except RuntimeError:
            if category == "all" and not city_filter["slug"]:
                raise
            try:
                html = await _download(client, _build_search_url(query.strip(), seller_type, "all", city_filter["slug"]))
            except RuntimeError:
                html = await _download(client, _build_search_url(query.strip(), seller_type, category, ""))

        listings = _extract_from_next_data(html) or _extract_fallback(html)
        listings = await _enrich_listings(client, listings[: limit * 2])
    
    listings = _filter_by_category_url(listings, category)
    listings = _filter_by_relevance(listings, query, category)
    listings = _filter_by_city(listings, city_filter["tokens"])

    min_price_uah = await _convert_to_uah(min_price, price_currency)
    max_price_uah = await _convert_to_uah(max_price, price_currency)
    filtered = _filter_by_price(listings, min_price_uah, max_price_uah)
    
    filtered = _filter_by_seller_type(filtered, seller_type)

    reverse = sort == "desc"
    filtered.sort(key=lambda item: item.price_uah if item.price_uah is not None else 10**12, reverse=reverse)
    return [await _format_listing(item, price_currency) for item in filtered[:limit]]

async def get_listing_details(url: str) -> dict:
    async with httpx.AsyncClient(timeout=18, follow_redirects=True) as client:
        html = await _download(client, url)
        
    data = _next_data(html)
    if not data:
        return {
            "description": _fallback_description(html),
            "parameters": [],
            "title": _fallback_title(html),
            "price_text": _fallback_price(html),
            "url": url,
            "images": [_fallback_image(html)]
        }

    ad_data = None
    for item in _walk_dicts(data):
        if isinstance(item, dict) and item.get("id") and item.get("title") and (item.get("description") or item.get("parameters")):
            ad_data = item
            break
            
    if not ad_data:
        for item in _walk_for_ads(data):
            if _clean_listing_url(_absolute_url(item.get("url", ""))) == _clean_listing_url(url):
                ad_data = item
                break

    if not ad_data:
        return {
            "description": _fallback_description(html),
            "parameters": [],
            "url": url,
            "title": _fallback_title(html),
            "price_text": _fallback_price(html)
        }

    params = []
    if "parameters" in ad_data:
        for p in ad_data["parameters"]:
            if isinstance(p, dict):
                val = p.get("value")
                label = val.get("label", "") if isinstance(val, dict) else str(val)
                params.append({"label": p.get("name", ""), "value": label})

    return {
        "description": ad_data.get("description", "") or _fallback_description(html),
        "parameters": params,
        "title": ad_data.get("title") or _fallback_title(html),
        "price_text": _pick_price_text(ad_data) or _fallback_price(html),
        "location": _pick_location(ad_data) or _fallback_location(html),
        "images": [_normalize_image_url(p.get("link", "")) for p in ad_data.get("photos", []) if isinstance(p, dict) and p.get("link")],
        "url": url
    }

def parse_optional_price(value: str | None) -> int | None:
    if value is None: return None
    cleaned = re.sub(r"\s+", "", value.strip())
    if cleaned in {"", "-"}: return None
    if not cleaned.isdigit(): raise ValueError("Ціна має бути числом.")
    return int(cleaned)

async def _download(client: httpx.AsyncClient, url: str) -> str:
    await asyncio.sleep(random.uniform(0.01, 0.05))
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.olx.ua/",
        "Upgrade-Insecure-Requests": "1",
    }
    try:
        response = await client.get(url, headers=headers)
        if response.status_code == 403:
            raise RuntimeError("OLX тимчасово заблокував доступ (403). Спробуйте за хвилину.")
        response.raise_for_status()
        return response.text
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"Сервер OLX повернув помилку {exc.response.status_code}.") from exc
    except httpx.RequestError as exc:
        raise RuntimeError("Не вдалося підключитися до OLX. Перевірте інтернет.") from exc

def _build_search_url(query: str, seller_type: str, category: str, city_slug: str) -> str:
    category_path = CATEGORY_PATHS.get(category, CATEGORY_PATHS["all"]).strip("/")
    city_slug = city_slug.strip("/")
    parts = [BASE_URL]
    if category == "all" and city_slug: parts.append(city_slug)
    else:
        parts.append(category_path)
        if city_slug: parts.append(city_slug)
    url = "/".join(part.strip("/") for part in parts) + f"/q-{quote(re.sub(r'\s+', '-', query.strip().lower()))}/"
    params = {}
    if seller_type in {"private", "business"}: params["search[private_business]"] = seller_type
    return f"{url}?{urlencode(params)}" if params else url

def _resolve_city(city: str, city_query: str = "") -> dict:
    custom = city_query.strip()
    if custom:
        normalized = custom.lower()
        slug = CITY_ALIASES.get(normalized) or _city_slug(custom)
        tokens = tuple({normalized, slug, *re.split(r"[\s,-]+", normalized)})
        return {"slug": slug, "tokens": tokens}
    if city == "all": return {"slug": "", "tokens": ()}
    return {"slug": CITY_SLUGS.get(city, ""), "tokens": CITY_NAMES.get(city, ())}

def _city_slug(value: str) -> str:
    translit = {
        "а": "a", "б": "b", "в": "v", "г": "g", "ґ": "g", "д": "d", "е": "e", "є": "e",
        "ж": "zh", "з": "z", "и": "i", "і": "i", "ї": "i", "й": "y", "к": "k", "л": "l",
        "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch", "ь": "", "ы": "y",
        "э": "e", "ю": "yu", "я": "ya", "ъ": "",
    }
    text = "".join(translit.get(char, char) for char in value.lower())
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")

async def _enrich_listings(client: httpx.AsyncClient, listings: list[Listing]) -> list[Listing]:
    if not listings: return []
    return list(await asyncio.gather(*[_enrich_listing(client, l) for l in listings]))

async def _enrich_listing(client: httpx.AsyncClient, listing: Listing) -> Listing:
    try:
        if listing.image and listing.price: return listing
        html = await _download(client, listing.url)
        detail = _detail_listing_from_next_data(html, listing.url)
        price_text = (detail.price_text if detail else "") or _detail_price(html) or listing.price_text
        price, currency = _parse_price(price_text)
        image = (detail.image if detail else "") or _detail_image(html) or listing.image
        seller_type = (detail.seller_type if detail else "") or _detail_seller_type(html) or listing.seller_type
        return replace(listing, price_text=price_text, price=price, currency=currency,
                       price_uah=await _convert_to_uah(price, currency), image=image, seller_type=seller_type)
    except Exception: return listing

def _extract_from_next_data(html: str) -> list[Listing]:
    data = _next_data(html)
    if not data: return []
    listings, seen = [], set()
    for item in _walk_for_ads(data):
        title = str(item.get("title") or item.get("name") or "").strip()
        url = _clean_listing_url(_absolute_url(str(item.get("url") or item.get("href") or "")))
        if not title or not url or url in seen: continue
        seen.add(url)
        price_text = _pick_price_text(item)
        price, currency = _parse_price(price_text)
        listings.append(Listing(title=title, price_text=price_text, price=price, currency=currency,
                               price_uah=None, url=url, image=_pick_image(item), location=_pick_location(item),
                               date=str(item.get("createdTime") or item.get("lastRefreshTime") or item.get("date") or "").strip(),
                               seller_type=_pick_seller_type(item)))
    return listings

def _detail_listing_from_next_data(html: str, url: str) -> Listing | None:
    clean_url = _clean_listing_url(url)
    for item in _extract_from_next_data(html):
        if _clean_listing_url(item.url) == clean_url: return item
    return None

def _next_data(html: str) -> object | None:
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
    if not match: return None
    try: return json.loads(unescape(match.group(1)))
    except json.JSONDecodeError: return None

def _walk_dicts(value: object) -> Iterable[dict]:
    if isinstance(value, dict):
        yield value
        for child in value.values(): yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value: yield from _walk_dicts(child)

def _walk_for_ads(value: object) -> Iterable[dict]:
    if isinstance(value, dict):
        if value.get("title") and ("/obyavlenie/" in str(value.get("url") or value.get("href") or "")): yield value
        for child in value.values(): yield from _walk_for_ads(child)
    elif isinstance(value, list):
        for child in value: yield from _walk_for_ads(child)

def _pick_price_text(item: dict) -> str:
    for k in ("price", "displayPrice", "priceText", "formattedPrice"):
        v = _price_candidate_to_text(item.get(k))
        if v: return v
    return ""

def _price_candidate_to_text(candidate: object) -> str:
    if isinstance(candidate, dict):
        for key in ("displayValue", "value", "regularPrice", "label"):
            v = _price_candidate_to_text(candidate.get(key))
            if v: return v
    elif isinstance(candidate, (str, int, float)): return str(candidate).strip()
    return ""

def _pick_location(item: dict) -> str:
    for k in ("location", "cityName", "city", "regionName"):
        c = item.get(k)
        if isinstance(c, dict):
            text = " ".join(str(c.get(key) or "").strip() for key in ("name", "cityName", "regionName"))
            if text.strip(): return re.sub(r"\s+", " ", text).strip()
        elif c: return str(c).strip()
    return ""

def _pick_image(item: dict) -> str:
    for key in ("photos", "images", "gallery", "image", "photo", "thumbnail"):
        image = _first_image_url(item.get(key))
        if image: return image
    return _first_image_url(item)

def _first_image_url(value: object) -> str:
    if isinstance(value, str) and _looks_like_image_url(value): return _normalize_image_url(value)
    if isinstance(value, list):
        for child in value:
            img = _first_image_url(child)
            if img: return img
    if isinstance(value, dict):
        for key in ("link", "url", "src", "href", "original"):
            img = _first_image_url(value.get(key))
            if img: return img
    return ""

def _looks_like_image_url(value: str) -> bool:
    v = _normalize_escaped_url(value)
    return v.startswith(("http", "//")) and "olxcdn.com" in v

def _normalize_escaped_url(value: str) -> str:
    return unescape(value).strip().strip('"').strip("'").replace("\\/", "/").replace("&amp;", "&")

def _normalize_image_url(value: str) -> str:
    v = _normalize_escaped_url(value)
    return f"https:{v}" if v.startswith("//") else v

def _pick_seller_type(item: dict) -> str:
    user = item.get("user")
    if isinstance(user, dict):
        is_bus = user.get("is_business")
        if is_bus is True: return "business"
        if is_bus is False: return "private"
    explicit = str(item.get("private_business") or item.get("sellerType") or "").lower()
    if explicit in {"private", "person", "owner"}: return "private"
    if explicit in {"business", "company", "shop"}: return "business"
    return "unknown"

def _detail_price(html: str) -> str:
    data = _next_data(html)
    if data:
        for item in _walk_dicts(data):
            p = _pick_price_text(item)
            if p and _parse_price(p)[0]: return p
    match = re.search(r"\d[\d\s.,]{2,}\s*(?:грн|₴|uah|usd|eur|\$|€)", _strip_tags(html), re.I)
    return match.group(0).strip() if match else ""

def _detail_image(html: str) -> str:
    data = _next_data(html)
    return _first_image_url(data) if data else _fallback_image(html)

def _detail_seller_type(html: str) -> str:
    data = _next_data(html)
    if data:
        for item in _walk_dicts(data):
            st = _pick_seller_type(item)
            if st != "unknown": return st
    return "business" if "бізнес" in html.lower() else "private" if "приват" in html.lower() else ""

def _extract_fallback(html: str) -> list[Listing]:
    listings, seen = [], set()
    for match in re.finditer(r'href="([^"]*/(?:d/uk/)?obyavlenie/[^"]+)"', html):
        url = _clean_listing_url(_absolute_url(unescape(match.group(1))))
        if url in seen: continue
        seen.add(url)
        listings.append(Listing(title=_fallback_title(html[match.start():match.start()+5000]), 
                               price_text=_fallback_price(html[match.start():match.start()+5000]),
                               price=None, currency="UAH", price_uah=None, url=url, 
                               image=_fallback_image(html[match.start():match.start()+5000]),
                               location=_fallback_location(html[match.start():match.start()+5000]),
                               date=_fallback_date(html[match.start():match.start()+5000]),
                               seller_type="unknown"))
    return listings

def _fallback_title(block: str) -> str:
    m = re.search(r'alt="([^"]+)"', block) or re.search(r"<h[3-6][^>]*>(.*?)</h", block, re.S)
    return _strip_tags(m.group(1)) if m else ""

def _fallback_price(block: str) -> str:
    m = re.search(r"\d[\d\s.,]{2,}\s*(?:грн|₴|uah|usd|eur|\$|€)", _strip_tags(block), re.I)
    return m.group(0).strip() if m else ""

def _fallback_image(block: str) -> str:
    m = re.search(r'(https?://[^"\']+olxcdn\.com[^"\']+)', block) or re.search(r'(//[^"\']+olxcdn\.com[^"\']+)', block)
    return _normalize_image_url(m.group(1)) if m else ""

def _fallback_location(block: str) -> str:
    for tokens in CITY_NAMES.values():
        for t in tokens:
            if t in block.lower(): return t.title()
    return ""

def _fallback_date(block: str) -> str:
    m = re.search(rf"(сьогодні|вчора|\d{{1,2}}\s+(?:січня|лютого|травня|грудня))", _strip_tags(block), re.I)
    return m.group(1).strip() if m else ""

def _fallback_description(html: str) -> str:
    m = re.search(r'data-testimonial-id="ad_description"[^>]*>(.*?)</div>', html, re.S) or \
        re.search(r'class="[^"]*details-description-text[^"]*"[^>]*>(.*?)</div>', html, re.S)
    return _strip_tags(m.group(1)) if m else ""

def _strip_tags(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", value))).strip()

def _filter_by_category_url(listings: Iterable[Listing], category: str) -> list[Listing]:
    if category == "all": return list(listings)
    path = CATEGORY_PATHS.get(category)
    return [l for l in listings if f"/{path}/" in l.url] if path else list(listings)

def _filter_by_price(listings: Iterable[Listing], min_p: int | None, max_p: int | None) -> list[Listing]:
    res = []
    for l in listings:
        if l.price_uah is None: continue
        if (min_p is None or l.price_uah >= min_p) and (max_p is None or l.price_uah <= max_p): res.append(l)
    return res

def _filter_by_seller_type(listings: Iterable[Listing], st: str) -> list[Listing]:
    if st not in {"private", "business"}: return list(listings)
    return [l for l in listings if l.seller_type in {st, "unknown"}]

def _filter_by_relevance(listings: Iterable[Listing], query: str, category: str) -> list[Listing]:
    words = [w for w in re.findall(r"[a-zа-яііїєґ0-9]+", query.lower()) if len(w) > 1]
    res = [l for l in listings if all(w in l.title.lower() for w in words[:2])]
    return res or list(listings)

def _filter_by_city(listings: Iterable[Listing], tokens: Iterable[str]) -> list[Listing]:
    tokens = [t.lower() for t in tokens if t]
    if not tokens: return list(listings)
    return [l for l in listings if any(t in l.location.lower() for t in tokens)] or list(listings)

async def _format_listing(item: Listing, disp_curr: str) -> dict:
    payload = asdict(item)
    disp_curr = disp_curr if disp_curr in {"UAH", "USD", "EUR"} else "UAH"
    amt = await _convert_from_uah(item.price_uah, disp_curr)
    payload["display_price_text"] = _format_money(amt, disp_curr)
    payload["price_uah_text"] = _format_money(item.price_uah, "UAH")
    payload["original_price_text"] = _format_money(item.price, item.currency) if item.price else item.price_text
    payload["exchange_rate_text"] = await _rate_text(item.currency)
    return payload

def _parse_price(price_text: str) -> tuple[int | None, str]:
    if not price_text: return None, "UAH"
    t = unescape(str(price_text)).lower()
    curr = "USD" if "$" in t or "usd" in t else "EUR" if "€" in t or "eur" in t else "UAH"
    m = re.search(r"\d[\d\s.,]*", t)
    return (int(re.sub(r"\D+", "", m.group(0))), curr) if m else (None, curr)

async def _convert_to_uah(amt: int | None, curr: str) -> int | None:
    if amt is None or curr == "UAH": return amt
    rate = (await _exchange_rates()).get(curr.upper())
    return round(amt * rate) if rate else amt

async def _convert_from_uah(amt: int | None, curr: str) -> int | None:
    if amt is None or curr == "UAH": return amt
    rate = (await _exchange_rates()).get(curr.upper())
    return round(amt / rate) if rate else amt

async def _rate_text(curr: str) -> str:
    if curr == "UAH": return ""
    rate = (await _exchange_rates()).get(curr.upper())
    return f"1 {curr} = {_format_money(round(rate), 'UAH')}" if rate else ""

_RATES_CACHE, _RATES_EXPIRY = {}, 0

async def _exchange_rates() -> dict[str, float]:
    global _RATES_EXPIRY, _RATES_CACHE
    now = asyncio.get_event_loop().time()
    if _RATES_CACHE and now < _RATES_EXPIRY: return _RATES_CACHE
    rates = {"USD": 41.5, "EUR": 45.0}
    rates.update(await _privat_rates())
    if set(rates) < {"USD", "EUR"}: rates.update(await _nbu_rates())
    _RATES_CACHE, _RATES_EXPIRY = rates, now + 3600
    return rates

async def _privat_rates() -> dict:
    try:
        data = await _json_url("https://api.privatbank.ua/p24api/pubinfo?exchange&coursid=5", 8)
        return {str(i["ccy"]): float(i["sale"]) for i in data if str(i.get("ccy")) in {"USD", "EUR"}}
    except Exception: return {}

async def _nbu_rates() -> dict:
    try:
        data = await _json_url("https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?json", 8)
        return {str(i["cc"]): float(i["rate"]) for i in data if str(i.get("cc")) in {"USD", "EUR"}}
    except Exception: return {}

async def _json_url(url: str, timeout: int) -> object:
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.get(url, headers={"User-Agent": random.choice(USER_AGENTS)})
        return r.json()

def _format_money(amt: int | None, curr: str) -> str:
    if amt is None: return "Ціну не вказано"
    v = f"{amt:,}".replace(",", " ")
    return f"${v}" if curr == "USD" else f"€{v}" if curr == "EUR" else f"{v} ₴"

def _absolute_url(url: str) -> str:
    u = _normalize_escaped_url(url)
    if u.startswith("http"): return u
    return f"https://www.olx.ua{u if u.startswith('/') else '/' + u}"

def _clean_listing_url(url: str) -> str:
    return url.split("?")[0]
