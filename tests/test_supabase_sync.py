"""Tests unitaires des règles de fusion SQLite/Supabase (sans accès réseau)."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from supabase_sync import FIELDS, merge_record, snapshot


def fiche():
    row = {field: "" for field in FIELDS}
    row.update({
        "siret": "TEST-001",
        "siege": 0,
        "approx": 0,
        "rel": 2,
        "adeq": 0,
        "masquer": 0,
        "lat": None,
        "lon": None,
        "overrides": {},
        "updated_at": "2026-01-01 00:00:00",
    })
    return row


class TestFusionTroisVoies(unittest.TestCase):
    def setUp(self):
        self.base = fiche()
        self.state = {"snapshot": snapshot(self.base)}

    def test_modification_distante_recuperee(self):
        local = copy.deepcopy(self.base)
        remote = copy.deepcopy(self.base)
        remote["ville"] = "Lorgues"

        merged, conflicts = merge_record("TEST-001", local, remote, self.state)

        self.assertEqual(conflicts, [])
        self.assertEqual(merged["ville"], "Lorgues")

    def test_modification_locale_conservee(self):
        local = copy.deepcopy(self.base)
        remote = copy.deepcopy(self.base)
        local["note"] = "À rappeler"

        merged, conflicts = merge_record("TEST-001", local, remote, self.state)

        self.assertEqual(conflicts, [])
        self.assertEqual(merged["note"], "À rappeler")

    def test_modifications_sur_champs_differents_fusionnees(self):
        local = copy.deepcopy(self.base)
        remote = copy.deepcopy(self.base)
        local["note"] = "Note locale"
        remote["ville"] = "Lorgues"

        merged, conflicts = merge_record("TEST-001", local, remote, self.state)

        self.assertEqual(conflicts, [])
        self.assertEqual(merged["note"], "Note locale")
        self.assertEqual(merged["ville"], "Lorgues")

    def test_modifications_concurrentes_du_meme_champ_signalees(self):
        local = copy.deepcopy(self.base)
        remote = copy.deepcopy(self.base)
        local["nom"] = "Nom local"
        remote["nom"] = "Nom distant"

        merged, conflicts = merge_record("TEST-001", local, remote, self.state)

        self.assertEqual(conflicts, ["nom"])

    def test_correction_manuelle_distante_prioritaire(self):
        local = copy.deepcopy(self.base)
        remote = copy.deepcopy(self.base)
        local["nom"] = "Nom automatique local"
        remote["nom"] = "Nom corrigé par le professeur"
        remote["overrides"] = {"nom": True}

        merged, conflicts = merge_record("TEST-001", local, remote, self.state)

        self.assertEqual(conflicts, [])
        self.assertEqual(merged["nom"], "Nom corrigé par le professeur")

    def test_updated_at_ne_cree_pas_de_conflit(self):
        local = copy.deepcopy(self.base)
        remote = copy.deepcopy(self.base)
        local["updated_at"] = "2026-02-01 00:00:00"
        remote["updated_at"] = "2026-03-01 00:00:00"

        merged, conflicts = merge_record("TEST-001", local, remote, self.state)

        self.assertEqual(conflicts, [])


if __name__ == "__main__":
    unittest.main()
