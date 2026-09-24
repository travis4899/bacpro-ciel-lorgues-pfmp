"""Lien de chaque lieu avec le référentiel du bac pro CIEL (arrêté 2023, annexe II « Référentiel des activités
professionnelles »). Calculé par grist_sync.py au moment de publier la carte : rien n'est stocké dans Grist.

Pôles et activités du référentiel :
  E  Réalisation et maintenance de produits électroniques
     E1 étude et conception · E2 tests et essais · E3 production et assemblage · E4 intégration matérielle et logicielle
     E5 maintenance et réparation
  R  Mise en œuvre de réseaux informatiques
     R1 accompagnement du client · R2 installation et qualification · R3 exploitation et maintien en condition
     opérationnelle · R5 maintenance des réseaux
  D  Valorisation de la donnée et cybersécurité
     D1 cahier des charges · D2 développement et validation de solutions logicielles · D3 gestion d'incidents

Niveau d'adéquation (adeq) :
  4  Stage CIEL déjà réalisé (preuve la plus forte)
  3  Cœur du référentiel (activité principale = un pôle CIEL)
  2  Activités CIEL possibles (service informatique d'une grande structure, courants faibles, alarmes…)
  1  Lien partiel (électricité générale, commerce, bureau d'études…)
  0  Hors référentiel
"""
import re
import unicodedata

ACTIVITES = {
    "E1": "Étude et conception de produits électroniques", "E2": "Tests et essais",
    "E3": "Production et assemblage d'ensembles électroniques", "E4": "Intégration matérielle et logicielle",
    "E5": "Maintenance et réparation de produits électroniques",
    "R1": "Accompagnement du client", "R2": "Installation et qualification",
    "R3": "Exploitation et maintien en condition opérationnelle", "R5": "Maintenance des réseaux informatiques",
    "D1": "Élaboration et appropriation d'un cahier des charges", "D2": "Développement et validation de solutions logicielles",
    "D3": "Gestion d'incidents",
}

# Code NAF (ou préfixe) -> (niveau, activités). Le préfixe le plus long l'emporte.
NAF = {
    # Électronique : fabrication, intégration, réparation (emplois : monteur-câbleur, opérateur CMS, réparation…)
    "26": (3, "E1 E2 E3 E4"), "26.51": (3, "E1 E2 E4"), "27.1": (3, "E2 E3"), "27.3": (3, "E3"), "27.9": (3, "E2 E3"),
    "27.2": (3, "E2 E3"), "29.31": (3, "E2 E3 E4"), "30.30": (3, "E2 E3 E4"), "33.13": (3, "E2 E5"), "33.14": (2, "E5"),
    "33.20C": (3, "E4 R2"), "33.20D": (3, "E4 R2"), "95.12": (3, "E5 R1"), "95.21": (3, "E5 R1"), "95.22": (2, "E5"),
    # Réseaux, télécoms, fibre, sécurité électronique (technicien d'installation / maintenance réseaux, alarmes…)
    "61": (3, "R1 R2 R3 R5"), "42.22": (3, "R2 R5"), "80.20": (3, "R2 R5 E5"), "95.11": (3, "R1 R5 E5"),
    "62.03": (3, "R3 R5 D3"), "62.02B": (3, "R3 R5 D3"), "63.11": (3, "R3 D2 D3"),
    "47.41": (3, "R1 E5"), "47.42": (3, "R1"), "47.43": (2, "R1 E5"), "46.51": (2, "R1"), "46.52": (2, "R1 E3"),
    # Données et cybersécurité (développement, cahier des charges, incidents)
    "62.01": (3, "D1 D2"), "62.02A": (3, "D1 D2 D3 R3"), "62.09": (3, "R3 D3"), "58.2": (3, "D1 D2"), "63.12": (2, "D2"),
    # Liens partiels
    "43.21": (1, "R2"), "43.22": (1, ""), "71.12": (1, "E1 D1"), "71.20": (1, "E2"), "46.66": (1, "R1"),
    "35.1": (2, "R3 R5"),  # énergie : réseaux de distribution, supervision (ex. Enedis)
}
# Mots du nom qui révèlent des activités CIEL chez un électricien ou une entreprise « autre »
MOTS = [
    (r"CYBER|SECURITE (INFORMATIQUE|NUMERIQUE)|PENTEST", 3, "D3 R3"),
    (r"INFORMATIQU|NUMERIQU|DIGITAL|LOGICIEL|\bSOFT|\bDATA\b|\bCLOUD\b|\bWEB\b", 3, "R1 R3 D2"),
    (r"RESEAU|TELECOM|FIBRE|FTTH|TELEPHON|\bRADIO\b|ANTENNIST|\bANTENNES\b|ANTENNE (TV|TELE|SATELLITE|NUMERIQUE|SERVICE)", 3, "R2 R5"),
    (r"ELECTRONI|AUTOMATISM|DOMOTI|ROBOT|MECATRONI", 3, "E4 E5"),
    (r"ALARME|VIDEO ?SURVEILL|VIDEOPROTECT|INCENDIE|COURANTS? FAIBLES?|CONTROLE D.ACCES|SURETE", 2, "R2 R5"),
]
# Structures où un service informatique (DSI) est probable : sièges, grands sites, collectivités, hôpitaux
CAT_DSI = {"grande": (2, "R3 R5 D3"), "public": (2, "R3 R5 D3"), "sante": (2, "R3 R5 D3")}
PROCHES = ("26", "27", "33", "42", "43", "46", "47", "58", "61", "62", "63", "70", "71", "74", "80", "82", "95")
ROLE_IT = re.compile(r"informatique|service informatique|\bit\b|réseau|reseau|système|systeme|analyste|développ|develop", re.I)


_TRANCHES = ("00", "01", "02", "03", "11", "12", "21", "22", "31", "32", "41", "42", "51", "52", "53")


def _au_moins(t, seuil):
    """Tranche d'effectif INSEE >= seuil ; « NN » (non renseigné) ou vide -> False."""
    return t in _TRANCHES and t >= seuil


def _nrm(s):
    return unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().upper()


def evaluer(l):
    """l : lieu (dict de grist_sync). -> (adeq 0-4, pôles « E R D », activités « E5 R1 … »)."""
    niveau, acts = 0, set()
    naf = l.get("naf") or ""
    cle = max((k for k in NAF if naf.startswith(k)), key=len, default=None)
    if cle:
        n, a = NAF[cle]
        niveau, acts = n, set(a.split())
    nom = _nrm(f'{l.get("nom", "")} {l.get("ens", "")} {l.get("osm_type", "")}')
    for motif, n, a in MOTS:
        if re.search(motif, nom):
            # le nom seul ne suffit pas pour un secteur sans rapport (code NAF connu et éloigné) : plafonné à 1
            proche = not naf or naf.startswith(PROCHES)
            niveau = max(niveau, n if proche else min(n, 1))
            acts |= set(a.split())
            break
    dsi = l.get("cat") == "grande" or (l.get("cat") in CAT_DSI and _au_moins(l.get("t") or "", "21"))
    if dsi:
        n, a = CAT_DSI.get(l.get("cat"), (2, "R3 R5 D3"))
        if niveau < n:
            niveau, acts = n, acts | set(a.split())
    if l.get("stage"):
        niveau = 4
        if ROLE_IT.search(l["stage"]):
            acts |= {"R3", "R5", "D3"}
    acts = sorted(acts, key=lambda x: ("ERD".index(x[0]), x))
    poles = " ".join(p for p in "ERD" if any(a.startswith(p) for a in acts))
    return niveau, poles, " ".join(acts)


# ================================================================ périmètre métiers (choix de l'enseignant)
# Seuls les lieux rattachés à au moins une de ces familles sont publiés sur la carte
# (sauf stage déjà réalisé ou ajout manuel dans Grist, toujours conservés).
FAMILLES = {
    "SI": "Systèmes d'information & DSI",
    "RT": "Réseaux & télécoms",
    "CF": "Courants faibles & sûreté",
    "EL": "Électronique & bureau d'études",
    "CY": "Cybersécurité",
}
_F_NAF = {  # préfixe NAF -> familles
    "62": "SI", "63.1": "SI", "58.2": "SI", "95.11": "SI", "47.41": "SI", "46.51": "SI",
    "62.02B": "SI RT", "62.03": "SI RT", "61": "RT", "42.22": "RT", "47.42": "RT", "95.12": "RT EL",
    "80.20": "CF", "26": "EL", "27.1": "EL", "27.3": "EL", "27.9": "EL", "29.31": "EL", "30.30": "EL",
    "27.2": "EL", "33.13": "EL", "33.20C": "EL CF", "33.20D": "EL CF", "95.21": "EL", "46.52": "EL RT",
}
_F_MOTS = [
    (r"CYBER|SECURITE (INFORMATIQUE|NUMERIQUE|DES SI|DES SYSTEMES)|PENTEST|\bSOC\b|\bRSSI\b|AUDIT (SECURITE|INFORMATIQUE)", "CY SI"),
    (r"INFORMATIQU|NUMERIQU|LOGICIEL|\bSOFT|\bDATA\b|\bCLOUD\b|\bDSI\b|SYSTEMES? D.INFORMATION|INFOGERANCE", "SI"),
    (r"RESEAU|TELECOM|FIBRE|FTTH|TELEPHON|ANTENNIST|\bANTENNES\b|ANTENNE (TV|TELE|SATELLITE|NUMERIQUE|SERVICE)|\bRADIO\b|\bWIFI\b|\b5G\b|\bVDI\b", "RT"),
    (r"ALARME|SURETE|VIDEO ?SURVEILL|VIDEOPROTECT|INCENDIE|COURANTS? FAIBLES?|CONTROLE D.ACCES|DOMOTI|INTRUSION|TELESURVEILL", "CF"),
    (r"ELECTRONI|AUTOMATISM|ROBOTI|MECATRONI|EMBARQU|\bIOT\b|INSTRUMENTATION|CARTES? ELECTRONIQUES?", "EL"),
]
# Bureaux d'études et électriciens : seulement si le nom montre une activité du périmètre
_SI_MOTS_SEULEMENT = ("43.21", "43.22", "71.12", "71.20", "33.14", "95.22", "33.12", "72.19", "32.50")


def familles(l):
    """-> ensemble de codes FAMILLES. Vide = hors périmètre."""
    naf = l.get("naf") or ""
    nom = _nrm(f'{l.get("nom", "")} {l.get("ens", "")} {l.get("osm_type", "")}')
    fam = set()
    cle = max((k for k in _F_NAF if naf.startswith(k)), key=len, default=None)
    if cle:
        fam |= set(_F_NAF[cle].split())
    for motif, f in _F_MOTS:
        if re.search(motif, nom):
            # le nom compte pour un secteur voisin (électricien, bureau d'études, commerce…) ou un NAF inconnu
            if (not naf or naf.startswith(PROCHES) or naf.startswith(_SI_MOTS_SEULEMENT)
                    or l.get("cat") in ("grande", "public", "sante", "cyber", "info", "tele", "elec", "secu")):
                fam |= set(f.split())
    cat, t, tu = l.get("cat"), l.get("t") or "", l.get("tu") or ""
    grand_siege = bool(l.get("siege")) and _au_moins(tu, "32")
    if naf.startswith("85.4") and (l.get("siege") or _au_moins(t, "21")):
        fam.add("SI")                                  # université, IUT, école d'ingénieurs : DSI
        if grand_siege or _au_moins(t, "32"):
            fam.add("CY")
    if cat == "grande" or (cat in ("public", "sante") and _au_moins(t, "21")):
        fam.add("SI")                                  # service informatique / DSI probable
        if grand_siege or _au_moins(t, "32"):
            fam.add("CY")                              # siège ou site de 250 salariés et plus : RSSI, sécurité du SI
    if l.get("osm_type") in ("Boutique informatique", "Dépannage informatique", "Entreprise informatique"):
        fam.add("SI")
    if l.get("osm_type") in ("Boutique télécoms", "Entreprise télécoms", "Magasin / réparation de téléphones"):
        fam.add("RT")
    if l.get("osm_type") == "Réparation électronique":
        fam.add("EL")
    return fam
