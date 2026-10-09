import os
import io
import requests
from dotenv import load_dotenv

load_dotenv()

SHORTIO_LINK_API_KEY = os.getenv("SHORTIO_LINK_API_KEY")
SHORTIO_DOMAIN = os.getenv("SHORTIO_DOMAIN")

BASE_API_URL = "https://api.short.io/links"
STATS_API_URL = "https://statistics.short.io/statistics/link"


def get_headers():
    return {
        "Authorization": SHORTIO_LINK_API_KEY,
        "Content-Type": "application/json",
        "accept": "application/json"
    }


def extract_path(short_url_or_path: str) -> str:
    """Extracts the slug / path from a full URL or returns the path directly."""
    cleaned = short_url_or_path.strip()
    if "/" in cleaned:
        cleaned = cleaned.rstrip("/").split("/")[-1]
    return cleaned


def shorten_url(long_url: str, custom_alias: str = None, title: str = None) -> dict:
    """
    Shortens a single long URL using Short.io API.
    Optionally accepts a custom alias (path) and a title.
    Returns a dictionary with status and result details.
    """
    payload = {
        "domain": SHORTIO_DOMAIN,
        "originalURL": long_url,
    }
    if custom_alias:
        payload["path"] = custom_alias.strip()
    if title:
        payload["title"] = title.strip()

    try:
        response = requests.post(BASE_API_URL, json=payload, headers=get_headers(), timeout=10)
        data = response.json()
        if response.status_code in (200, 201):
            return {
                "success": True,
                "shortURL": data.get("shortURL") or data.get("secureShortURL"),
                "idString": data.get("idString") or data.get("id"),
                "originalURL": data.get("originalURL"),
                "path": data.get("path")
            }
        else:
            message = data.get("message") or data.get("error") or str(data)
            return {
                "success": False,
                "error": message,
                "status_code": response.status_code
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def shorten_multiple_urls(urls: list) -> dict:
    """
    Shortens multiple URLs in bulk using Short.io Bulk API (POST /links/bulk).
    Returns a dictionary with results list.
    """
    if not urls:
        return {"success": False, "error": "No URLs provided.", "results": []}

    url = f"{BASE_API_URL}/bulk"
    payload = {
        "domain": SHORTIO_DOMAIN,
        "links": [{"originalURL": u.strip()} for u in urls if u.strip()]
    }

    try:
        response = requests.post(url, json=payload, headers=get_headers(), timeout=15)
        if response.status_code in (200, 201):
            data = response.json()
            results = []
            for item in data:
                short_url = item.get("shortURL") or item.get("secureShortURL")
                results.append({
                    "success": item.get("success", True),
                    "originalURL": item.get("originalURL"),
                    "shortURL": short_url,
                    "idString": item.get("idString") or item.get("id"),
                    "error": item.get("error") or item.get("message")
                })
            return {
                "success": True,
                "results": results
            }
        else:
            try:
                data = response.json()
                message = data.get("message") or data.get("error") or str(data)
            except Exception:
                message = response.text or f"HTTP {response.status_code}"
            return {
                "success": False,
                "error": message,
                "results": []
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "results": []
        }


def expand_url(short_url_or_path: str) -> dict:
    """
    Expands a Short.io short link to its original URL and retrieves link details.
    """
    path = extract_path(short_url_or_path)
    url = f"{BASE_API_URL}/expand"
    params = {
        "domain": SHORTIO_DOMAIN,
        "path": path
    }

    try:
        response = requests.get(url, params=params, headers=get_headers(), timeout=10)
        data = response.json()
        if response.status_code == 200 and "originalURL" in data:
            return {
                "success": True,
                "originalURL": data.get("originalURL"),
                "shortURL": data.get("shortURL") or data.get("secureShortURL"),
                "idString": data.get("idString") or data.get("id"),
                "path": data.get("path")
            }
        else:
            message = data.get("message") or data.get("error") or "Short link not found."
            return {
                "success": False,
                "error": message
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def update_short_url_slug(short_url_or_path: str, new_slug: str) -> dict:
    """
    Updates the slug / path of an existing Short.io short URL.
    POST /links/{linkIdString}
    """
    expand_res = expand_url(short_url_or_path)
    if not expand_res.get("success"):
        return {
            "success": False,
            "error": f"Could not find existing link: {expand_res.get('error', 'Not found')}"
        }

    link_id = expand_res.get("idString")
    old_slug = expand_res.get("path")
    clean_new_slug = extract_path(new_slug)

    url = f"{BASE_API_URL}/{link_id}"
    payload = {
        "path": clean_new_slug
    }

    try:
        response = requests.post(url, json=payload, headers=get_headers(), timeout=10)
        data = response.json()
        if response.status_code in (200, 201):
            return {
                "success": True,
                "shortURL": data.get("shortURL") or data.get("secureShortURL"),
                "new_slug": data.get("path"),
                "old_slug": old_slug,
                "originalURL": data.get("originalURL"),
                "idString": data.get("idString") or data.get("id")
            }
        else:
            message = data.get("message") or data.get("error") or str(data)
            return {
                "success": False,
                "error": message,
                "status_code": response.status_code
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def get_stats(short_url_or_path: str) -> dict:
    """
    Retrieves click statistics for a given short link or path.
    """
    expand_result = expand_url(short_url_or_path)
    if not expand_result.get("success"):
        return expand_result

    link_id = expand_result.get("idString")
    if not link_id:
        return {
            "success": False,
            "error": "Could not identify Link ID for stats lookup."
        }

    try:
        url = f"{STATS_API_URL}/{link_id}"
        params = {"period": "total"}
        response = requests.get(url, params=params, headers=get_headers(), timeout=10)
        data = response.json()
        if response.status_code == 200:
            return {
                "success": True,
                "shortURL": expand_result.get("shortURL"),
                "originalURL": expand_result.get("originalURL"),
                "totalClicks": data.get("totalClicks", 0),
                "humanClicks": data.get("humanClicks", 0)
            }
        else:
            return {
                "success": False,
                "error": data.get("message") or "Failed to retrieve statistics."
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def generate_qr_code(link_id_string: str, image_type: str = "png", use_domain_settings: bool = True) -> dict:
    """
    Generates a QR code for a given link ID using Short.io API.
    POST /links/qr/{linkIdString}
    Returns a dict containing image_bytes, qr_url, and success status.
    """
    url = f"{BASE_API_URL}/qr/{link_id_string}"
    payload = {
        "useDomainSettings": use_domain_settings,
        "type": image_type
    }
    try:
        response = requests.post(url, json=payload, headers=get_headers(), timeout=10)
        if response.status_code in (200, 201):
            try:
                data = response.json()
                qr_url = data.get("url")
                if qr_url:
                    img_resp = requests.get(qr_url, timeout=10)
                    if img_resp.status_code == 200:
                        return {
                            "success": True,
                            "qr_url": qr_url,
                            "image_bytes": img_resp.content,
                            "content_type": img_resp.headers.get("content-type", "image/png")
                        }
            except Exception:
                pass

            if response.content.startswith(b'\x89PNG') or b'<svg' in response.content:
                return {
                    "success": True,
                    "image_bytes": response.content,
                    "content_type": response.headers.get("content-type", "image/png")
                }

            return {
                "success": False,
                "error": "Invalid QR code image response from server."
            }
        else:
            try:
                data = response.json()
                message = data.get("message") or data.get("error") or str(data)
            except Exception:
                message = response.text or f"HTTP {response.status_code}"
            return {
                "success": False,
                "error": message
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def get_qr_for_url(input_url: str) -> dict:
    """
    Given either an existing short link or a new long URL,
    ensures the link exists on Short.io and generates its QR code image.
    """
    clean_url = input_url.strip()

    expand_res = expand_url(clean_url)
    if expand_res.get("success") and expand_res.get("idString"):
        qr_res = generate_qr_code(expand_res["idString"])
        if qr_res.get("success"):
            return {
                "success": True,
                "image_bytes": qr_res["image_bytes"],
                "qr_url": qr_res.get("qr_url"),
                "shortURL": expand_res.get("shortURL"),
                "originalURL": expand_res.get("originalURL")
            }
        return qr_res

    if clean_url.startswith("http://") or clean_url.startswith("https://"):
        shorten_res = shorten_url(clean_url)
        if shorten_res.get("success") and shorten_res.get("idString"):
            qr_res = generate_qr_code(shorten_res["idString"])
            if qr_res.get("success"):
                return {
                    "success": True,
                    "image_bytes": qr_res["image_bytes"],
                    "qr_url": qr_res.get("qr_url"),
                    "shortURL": shorten_res.get("shortURL"),
                    "originalURL": clean_url
                }
            return qr_res
        return shorten_res

    return {
        "success": False,
        "error": "Invalid URL or Short.io link not found."
    }
