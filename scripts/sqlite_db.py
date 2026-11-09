"""Accès à la base SQLite du projet PFMP Var.

La base est un fichier local versionné dans Git : database/entreprises.db.
Les pages GitHub ne lisent jamais ce fichier directement ; sqlite_sync.py produit le JSON public.
"""
import json
import sqlite3
from pathlib import Path
from config import ROOT

DB_DIR = ROOT / "database"
DB_PATH = DB_DIR / "entreprises.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS entreprises (
    siret TEXT PRIMARY KEY,
    nom TEXT NOT NULL DEFAULT '',
    ens TEXT NOT NULL DEFAULT '',
    adr TEXT NOT NULL DEFAULT '',
    cp TEXT NOT NULL DEFAULT '',
    ville TEXT NOT NULL DEFAULT '',
    naf TEXT NOT NULL DEFAULT '',
    t TEXT NOT NULL DEFAULT '',
    tu TEXT NOT NULL DEFAULT '',
    cat TEXT NOT NULL DEFAULT 'autre',
    src TEXT NOT NULL DEFAULT '',
    siege INTEGER NOT NULL DEFAULT 0,
    lat REAL,
    lon REAL,
    approx INTEGER NOT NULL DEFAULT 0,
    rel INTEGER NOT NULL DEFAULT 2,
    tel TEXT NOT NULL DEFAULT '',
    mail TEXT NOT NULL DEFAULT '',
    web TEXT NOT NULL DEFAULT '',
    csrc TEXT NOT NULL DEFAULT '',
    stage TEXT NOT NULL DEFAULT '',
    osm_type TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    adeq INTEGER NOT NULL DEFAULT 0,
    poles TEXT NOT NULL DEFAULT '',
    acts TEXT NOT NULL DEFAULT '',
    fam TEXT NOT NULL DEFAULT '',
    masquer INTEGER NOT NULL DEFAULT 0,
    statut_auto TEXT NOT NULL DEFAULT '',
    overrides TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_entreprises_ville ON entreprises(ville);
CREATE INDEX IF NOT EXISTS idx_entreprises_cp ON entreprises(cp);
CREATE INDEX IF NOT EXISTS idx_entreprises_naf ON entreprises(naf);
CREATE TABLE IF NOT EXISTS meta (
    cle TEXT PRIMARY KEY,
    valeur TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sync_state (
    siret TEXT PRIMARY KEY,
    remote_revision INTEGER NOT NULL,
    snapshot TEXT NOT NULL,
    synced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS sync_meta (
    cle TEXT PRIMARY KEY,
    valeur TEXT NOT NULL
);
INSERT OR IGNORE INTO meta(cle, valeur) VALUES ('schema_version', '1');
"""

AUTO_FIELDS = (
    "nom", "ens", "adr", "cp", "ville", "naf", "t", "tu", "cat", "src",
    "siege", "lat", "lon", "approx", "rel", "tel", "mail", "web", "csrc", "osm_type",
)


def connect():
    DB_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA journal_mode = DELETE")
    db.executescript(SCHEMA)
    return db


def champs_manuels(row):
    return json.loads(row["overrides"] or "{}")
