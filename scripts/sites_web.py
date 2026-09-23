"""Sites web des entreprises : découverte vérifiée + lecture des coordonnées publiées.

Découverte : pour une entreprise sans site connu, on essaie quelques noms de domaine plausibles
(nom de l'entreprise ou enseigne, en .fr / .com). Un site n'est retenu QUE si ses pages
(accueil ou mentions légales) contiennent le SIREN de l'entreprise, ou à la fois son nom et son code postal.

Lecture : sur un site retenu (ou connu via OSM / service-public), on lit la page d'accueil et une page
contact : liens tel: et mailto:, sinon numéros et adresses du même domaine écrits dans la page.
Rien n'est deviné : une adresse e-mail n'est jamais fabriquée.
"""
import re
import socket
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter

from api import UA

socket.setdefaulttimeout(8)
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; " + UA + ")", "Accept-Language": "fr"}
MAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
MAIL_EXCLUS = re.compile(r"(wix|sentry|example|domain|votre|email\.com|\.png|\.jpg|\.gif|\.webp|\.svg|godaddy|ovh\.net|jimdo|"
                         r"wordpress|squarespace|cloudflare|u00|placeholder|nom@|prenom|john|doe)", re.I)
TEL_RE = re.compile(r"(?<![\d.])(?:\+33\s?\(?0?\)?\s?|0)[1-9](?:[\s.\-]?\d{2}){4}(?![\d.])")
FORMES = {"SARL", "SAS", "SASU", "EURL", "SA", "SCI", "SNC", "SCOP", "SCA", "SELARL", "ETS", "ETABLISSEMENTS", "STE",
          "SOCIETE", "GROUPE", "FRANCE", "ET", "DE", "DU", "DES", "LA", "LE", "LES", "L", "D", "EN", "ENTREPRISE", "CIE"}


def nrm(s):
    return unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().upper()


def tel_fr(s):
    d = re.sub(r"\D", "", s or "")
    if d.startswith("0033"): d = "0" + d[4:]
    elif d.startswith("33") and len(d) == 11: d = "0" + d[2:]
    if len(d) == 10 and d[0] == "0" and d[1] != "0" and d[1] != "8":
        return " ".join(d[i:i + 2] for i in range(0, 10, 2))
    return ""


def domaine(u):
    h = urllib.parse.urlparse(u).hostname or ""
    return h[4:] if h.startswith("www.") else h


def telecharger(u, limite=600_000):
    req = urllib.request.Request(u, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=8) as h:
        if "html" not in (h.headers.get("Content-Type") or "html"):
            return "", h.geturl()
        return h.read(limite).decode("utf-8", "ignore"), h.geturl()


def lien(html, base, motif):
    m = re.search(r'href="([^"#]*(?:' + motif + r')[^"]*)"', html, re.I)
    return urllib.parse.urljoin(base, m.group(1)) if m else None


def texte(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", html)))


# ---------------------------------------------------------------- lecture des coordonnées
def lire_contacts(pages, dom):
    out = {"tel": "", "mail": ""}
    for p in pages:
        if not out["mail"]:
            mails = [urllib.parse.unquote(x).split("?")[0].strip() for x in re.findall(r'mailto:([^"\'>\s]+)', p, re.I)]
            mails += [x for x in MAIL_RE.findall(p) if dom and x.lower().endswith("@" + dom)]
            mails = [x for x in mails if MAIL_RE.fullmatch(x) and not MAIL_EXCLUS.search(x)]
            if mails: out["mail"] = mails[0].lower()
        if not out["tel"]:
            tels = [tel_fr(x) for x in re.findall(r'href="tel:([^"]+)"', p, re.I)] or [tel_fr(x) for x in TEL_RE.findall(texte(p))]
            tels = [x for x in tels if x]
            if tels: out["tel"] = Counter(tels).most_common(1)[0][0]
    return out


def visiter(u):
    """Coordonnées publiées sur un site connu (accueil + page contact)."""
    try:
        html, final = telecharger(u)
    except Exception:
        return {"tel": "", "mail": ""}
    pages = [html]
    c = lien(html, final, "contact")
    if c:
        try: pages.append(telecharger(c)[0])
        except Exception: pass
    return lire_contacts(pages, domaine(final))


# ---------------------------------------------------------------- découverte vérifiée
def candidats(noms):
    """Noms de domaine plausibles à partir de la dénomination / de l'enseigne."""
    out = []
    for nom in noms:
        mots = [m for m in re.findall(r"[A-Z0-9]+", nrm(re.sub(r"\(.*?\)", " ", nom))) if m not in FORMES]
        if not mots or (len(mots) == 1 and len(mots[0]) < 4):
            continue
        bases = ["".join(mots), "-".join(mots)]
        if len(mots) > 2: bases += ["".join(mots[:2]), "-".join(mots[:2])]
        for b in bases:
            if 4 <= len(b) <= 40:
                for tld in (".fr", ".com"):
                    d = b.lower() + tld
                    if d not in out: out.append(d)
    return out[:10]


def resout(d):
    try:
        socket.gethostbyname(d)
        return True
    except Exception:
        return False


def verifie(html, siren, nom, cps):
    t = nrm(texte(html))
    if re.search(r"\b" + r"\s?".join([siren[:3], siren[3:6], siren[6:]]) + r"\b", t):
        return "SIREN"
    mots = [m for m in re.findall(r"[A-Z0-9]{3,}", nrm(nom)) if m not in FORMES]
    if mots and all(m in t for m in mots[:3]) and any(re.search(r"\b" + cp + r"\b", t) for cp in cps):
        return "nom + code postal"
    return ""


def decouvrir(r):
    """Renvoie {'web', 'preuve', 'tel', 'mail'} ou {} si aucun site vérifié."""
    siren = r["siret"][:9]
    for d in candidats([r["nom"], r["ens"]] if r["ens"] else [r["nom"]]):
        if not resout(d) and not resout("www." + d):
            continue
        for u in ("https://www." + d, "https://" + d, "http://www." + d):
            try:
                html, final = telecharger(u)
            except Exception:
                continue
            if not html or domaine(final).split(".")[0] not in d:   # redirection vers un autre site : on ignore
                break
            pages = [html]
            preuve = verifie(html, siren, r["nom"], r["cps"])
            if not preuve:
                ml = lien(html, final, "mention|legal|cgv|a-propos|qui-sommes")
                if ml:
                    try:
                        pages.append(telecharger(ml)[0])
                        preuve = verifie(pages[-1], siren, r["nom"], r["cps"])
                    except Exception:
                        pass
            if not preuve:
                break
            c = lien(html, final, "contact")
            if c:
                try: pages.append(telecharger(c)[0])
                except Exception: pass
            return {"web": final.split("#")[0], "preuve": preuve, **lire_contacts(pages, domaine(final))}
    return {}
