import os
import sys
import webbrowser
from typing import Optional
from urllib.parse import unquote

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles

from parser import parse_optional_price, search_olx, get_listing_details

app = FastAPI(title="OLX Smart Search API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health():
    return {"ok": True, "service": "olx-parser", "version": 5}

@app.get("/api/search")
async def search(
    query: str,
    min_price: Optional[str] = "",
    max_price: Optional[str] = "",
    sort: str = "asc",
    seller_type: str = "all",
    category: str = "all",
    city: str = "all",
    city_query: str = "",
    price_currency: str = "UAH"
):
    try:
        items = await search_olx(
            query=query,
            min_price=parse_optional_price(min_price),
            max_price=parse_optional_price(max_price),
            sort=sort if sort in {"asc", "desc"} else "asc",
            seller_type=seller_type if seller_type in {"all", "private", "business"} else "all",
            category=category,
            city=city,
            city_query=city_query,
            price_currency=price_currency.upper() if price_currency.upper() in {"UAH", "USD", "EUR"} else "UAH",
        )
        return {"items": items}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.get("/api/details")
async def details(url: str):
    try:
        data = await get_listing_details(url)
        return data
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.get("/api/image")
async def proxy_image(url: str):
    url = unquote(url).strip()
    if not url.startswith(("https://", "http://")) or "olxcdn.com" not in url:
        raise HTTPException(status_code=400, detail="Bad image URL")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                    "Referer": "https://www.olx.ua/",
                },
                timeout=14
            )
            response.raise_for_status()
            return Response(content=response.content, media_type=response.headers.get("Content-Type", "image/jpeg"))
        except Exception:
            raise HTTPException(status_code=404, detail="Image not available")

@app.get("/")
async def index():
    return FileResponse("index.html")

# Serve static files
app.mount("/css", StaticFiles(directory="css"), name="css")
app.mount("/js", StaticFiles(directory="js"), name="js")

def main(open_browser: bool = False):
    port = int(os.environ.get("PORT", 8000))
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass

    url = f"http://127.0.0.1:{port}"
    print(f"OLX Smart Search running at {url}")
    
    if open_browser:
        webbrowser.open(url)
        
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")

if __name__ == "__main__":
    main()
