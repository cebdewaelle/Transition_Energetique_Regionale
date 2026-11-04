from datetime import date
from unittest.mock import MagicMock

import pyarrow as pa
import pytest
import requests

from transition_energetique_regionale import departements
from transition_energetique_regionale.departements import (
    calculer_centre_et_population,
)

COMMUNES = [
    {"population": 100, "centre": {"coordinates": [2.0, 50.0]}},
    {"population": 300, "centre": {"coordinates": [4.0, 48.0]}},
]


def ligne_departement(code="59"):
    return {
        "code_departement": code,
        "nom": "Nord",
        "code_region": "32",
        "longitude": 3.0,
        "latitude": 50.0,
        "population": 400,
        "date_extraction": date(2026, 1, 1),
    }


def test_calculer_centre_et_population():
    resultat = calculer_centre_et_population(COMMUNES)

    assert resultat == {"longitude": 3.0, "latitude": 49.0, "population": 400}


def test_le_centre_n_est_pas_pondere_par_la_population():
    communes = [
        {"population": 1, "centre": {"coordinates": [0.0, 40.0]}},
        {"population": 999, "centre": {"coordinates": [10.0, 50.0]}},
    ]

    resultat = calculer_centre_et_population(communes)

    assert resultat["longitude"] == 5.0
    assert resultat["latitude"] == 45.0


def test_calculer_centre_et_population_sans_commune():
    with pytest.raises(ValueError, match="Aucune commune"):
        calculer_centre_et_population([])


def test_les_12_regions_d_eco2mix_sont_couvertes():
    assert set(departements.CODES_REGIONS) == {
        "11",
        "24",
        "27",
        "28",
        "32",
        "44",
        "52",
        "53",
        "75",
        "76",
        "84",
        "93",
    }


def test_get_json_interroge_l_api_et_renvoie_la_reponse(monkeypatch):
    reponse = MagicMock()
    reponse.json.return_value = [{"code": "59"}]
    faux_get = MagicMock(return_value=reponse)
    monkeypatch.setattr(departements.requests, "get", faux_get)

    resultat = departements._get_json("/regions/32/departements", params={"a": "b"})

    assert resultat == [{"code": "59"}]
    assert faux_get.call_args.args[0] == (
        "https://geo.api.gouv.fr/regions/32/departements"
    )
    assert faux_get.call_args.kwargs["params"] == {"a": "b"}
    assert faux_get.call_args.kwargs["timeout"] > 0


def test_get_json_propage_les_erreurs_http(monkeypatch):
    reponse = MagicMock()
    reponse.raise_for_status.side_effect = requests.HTTPError("503")
    monkeypatch.setattr(departements.requests, "get", MagicMock(return_value=reponse))

    with pytest.raises(requests.HTTPError):
        departements._get_json("/departements")


def test_recuperer_departements_construit_une_ligne_par_departement(monkeypatch):
    monkeypatch.setattr(departements, "CODES_REGIONS", {"28": "Normandie"})

    def faux_get_json(chemin, params=None):
        if chemin == "/regions/28/departements":
            return [
                {"nom": "Calvados", "code": "14", "codeRegion": "28"},
                {"nom": "Eure", "code": "27", "codeRegion": "28"},
            ]
        assert params == {"fields": "population,centre"}
        return COMMUNES

    monkeypatch.setattr(departements, "_get_json", faux_get_json)

    lignes = departements.recuperer_departements()

    assert [ligne["code_departement"] for ligne in lignes] == ["14", "27"]
    assert lignes[0]["nom"] == "Calvados"
    assert lignes[0]["code_region"] == "28"
    assert lignes[0]["longitude"] == 3.0
    assert lignes[0]["latitude"] == 49.0
    assert lignes[0]["population"] == 400
    assert isinstance(lignes[0]["date_extraction"], date)


def test_les_lignes_respectent_le_schema_et_gardent_les_zeros_des_codes():
    table = pa.Table.from_pylist(
        [ligne_departement("01")], schema=departements.SCHEMA
    )

    assert table.schema == departements.SCHEMA
    assert table["code_departement"].to_pylist() == ["01"]
    assert set(ligne_departement()) == set(departements.SCHEMA.names)


def test_ecrire_table_refuse_un_nombre_de_departements_incorrect(monkeypatch):
    faux_catalogue = MagicMock(side_effect=AssertionError("catalogue appelé"))
    monkeypatch.setattr(departements, "charger_catalogue", faux_catalogue)

    with pytest.raises(ValueError, match="93 départements au lieu de 94"):
        departements.ecrire_table([ligne_departement()] * 93)

    faux_catalogue.assert_not_called()


def test_ecrire_table_remplace_le_contenu_de_la_table(monkeypatch):
    catalogue = MagicMock()
    monkeypatch.setattr(departements, "charger_catalogue", lambda: catalogue)

    departements.ecrire_table([ligne_departement()] * 94)

    catalogue.create_namespace_if_not_exists.assert_called_once_with("bronze")
    table = catalogue.create_table_if_not_exists.return_value
    assert catalogue.create_table_if_not_exists.call_args.args[0] == (
        "bronze.ref_departements"
    )
    table.overwrite.assert_called_once()
    assert table.overwrite.call_args.args[0].num_rows == 94
    table.append.assert_not_called()
