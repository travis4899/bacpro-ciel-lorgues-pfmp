"""Petits outils réseau : API Recherche d'entreprises (data.gouv) avec limite de débit et cache disque."""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://recherche-entreprises.api.gouv.fr/search"
UA = "carte-stages-ciel/1.0 (projet pedagogique bac pro CIEL, academie de Poitiers)"
_last = [0.0]


def http_json(url, params=None, timeout=30, delay=0.16, method="GET", data=None):
    """GET/POST JSON avec ~6 requêtes/s max et nouvelles tentatives (429, 5xx, coupures)."""
    if params:
        url += "?" + urllib.parse.urlencode(params)
    for attempt in range(6):
        wait = delay - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA}, method=method,
                                         data=data.encode() if isinstance(data, str) else data)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                time.sleep(2 + attempt * 2)
                continue
            raise
        except Exception:
            time.sleep(2)
    raise RuntimeError(f"Échec après 6 tentatives : {url}")


def search_all(params, max_pages=400):
    """Toutes les pages d'une recherche (25 résultats/page, 10 000 max côté API)."""
    out, page = [], 1
    while True:
        j = http_json(API, {**params, "per_page": 25, "page": page, "limite_matching_etablissements": 100})
        out += j["results"]
        if page >= j["total_pages"] or page >= max_pages:
            return out
        page += 1


def cached(path, producer):
    """Renvoie le JSON en cache ou le produit puis l'enregistre."""
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    path.parent.mkdir(parents=True, exist_ok=True)
    data = producer()
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data
