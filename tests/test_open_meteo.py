from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pyarrow as pa
import pytest
import requests
from pyiceberg.transforms import MonthTransform

from transition_energetique_regionale import open_meteo
from transition_energetique_regionale.open_meteo import transformer_reponse


@pytest.fixture
def reponse_api():
    """Réponse de l'API avec des valeurs toutes différentes pour détecter les inversions."""
    return {
        "latitude": 50.4,
        "longitude": 3.3,
        "elevation": 17.0,
        "hourly": {
            "time": ["2024-01-01T00:00", "2024-01-01T01:00"],
            "temperature_2m": [7.5, 7.4],
            "wind_speed_100m": [13.93, 13.87],
            "shortwave_radiation": [0.0, 44.0],
            "precipitation": [0.7, 1.2],
            "snowfall": [0.0, 0.14],
            "snow_depth": [0.0, 0.09],
        },
    }


@pytest.fixture
def periode_janvier(monkeypatch):
    monkeypatch.setitem(open_meteo.PERIODE, "debut", "2024-01-01")
    monkeypatch.setitem(open_meteo.PERIODE, "fin", "2024-01-31")
    monkeypatch.setattr(open_meteo, "NB_DEPARTEMENTS", 1)


# --- transformer_reponse ---


def test_une_ligne_par_heure_avec_le_code_departement(reponse_api):
    lignes = transformer_reponse("59", reponse_api)

    assert len(lignes) == 2
    assert all(ligne["code_departement"] == "59" for ligne in lignes)


def test_chaque_valeur_reste_sur_la_bonne_heure_et_la_bonne_colonne(reponse_api):
    ligne = transformer_reponse("59", reponse_api)[1]

    assert ligne["temperature_2m"] == 7.4
    assert ligne["wind_speed_100m"] == 13.87
    assert ligne["shortwave_radiation"] == 44.0
    assert ligne["precipitation"] == 1.2
    assert ligne["snowfall"] == 0.14
    assert ligne["snow_depth"] == 0.09


def test_horodatage_en_utc(reponse_api):
    ligne = transformer_reponse("59", reponse_api)[1]

    assert ligne["horodatage"] == datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc)
    assert ligne["horodatage"].utcoffset().total_seconds() == 0


def test_coordonnees_de_la_grille_sans_inversion(reponse_api):
    ligne = transformer_reponse("59", reponse_api)[0]

    assert ligne["latitude_grille"] == 50.4
    assert ligne["longitude_grille"] == 3.3
    assert ligne["altitude"] == 17.0


def test_date_extraction_est_une_date(reponse_api):
    ligne = transformer_reponse("59", reponse_api)[0]

    assert isinstance(ligne["date_extraction"], date)
    assert not isinstance(ligne["date_extraction"], datetime)


def test_valeur_vide_conservee_en_bronze(reponse_api):
    reponse_api["hourly"]["snow_depth"][0] = None

    assert transformer_reponse("59", reponse_api)[0]["snow_depth"] is None


def test_reponse_sans_heure_ne_produit_aucune_ligne(reponse_api):
    reponse_api["hourly"] = {"time": []}

    assert transformer_reponse("59", reponse_api) == []


def test_champ_manquant_provoque_une_erreur(reponse_api):
    del reponse_api["elevation"]

    with pytest.raises(KeyError, match="elevation"):
        transformer_reponse("59", reponse_api)


def test_les_lignes_respectent_le_schema(reponse_api):
    lignes = transformer_reponse("59", reponse_api)

    table = pa.Table.from_pylist(lignes, schema=open_meteo.SCHEMA)

    assert set(lignes[0]) == set(open_meteo.SCHEMA.names)
    assert table.num_rows == 2
    assert table.schema.field("horodatage").type == pa.timestamp("us", tz="UTC")


def test_chaque_variable_demandee_a_une_colonne():
    assert set(open_meteo.VARIABLES) <= set(open_meteo.SCHEMA.names)


# --- nb_lignes_attendues ---


@pytest.mark.parametrize(
    ("debut", "fin", "nb_departements", "attendu"),
    [
        pytest.param("2024-01-01", "2024-01-01", 1, 24, id="un_jour"),
        pytest.param("2024-01-01", "2024-01-31", 1, 744, id="janvier"),
        pytest.param("2024-02-01", "2024-02-29", 1, 696, id="fevrier_bissextile"),
        pytest.param("2024-03-31", "2024-03-31", 1, 24, id="changement_heure_ete"),
        pytest.param("2024-10-27", "2024-10-27", 1, 24, id="changement_heure_hiver"),
        pytest.param("2024-01-01", "2024-12-31", 94, 825_696, id="annee_2024"),
        pytest.param("2024-01-01", "2025-12-31", 94, 1_649_136, id="2024_et_2025"),
    ],
)
def test_nb_lignes_attendues(
    debut: str, fin: str, nb_departements: int, attendu: int
) -> None:
    assert open_meteo.nb_lignes_attendues(nb_departements, debut, fin) == attendu


# --- recuperer_meteo ---


def test_recuperer_meteo_envoie_les_bons_parametres(monkeypatch):
    reponse = MagicMock()
    reponse.json.return_value = {"hourly": {}}
    faux_get = MagicMock(return_value=reponse)
    monkeypatch.setattr(open_meteo.requests, "get", faux_get)

    resultat = open_meteo.recuperer_meteo(3.3, 50.4, "2024-01-01", "2024-01-31")

    assert resultat == {"hourly": {}}
    assert faux_get.call_args.args[0] == open_meteo.API_METEO
    params = faux_get.call_args.kwargs["params"]
    assert params["longitude"] == 3.3
    assert params["latitude"] == 50.4
    assert params["start_date"] == "2024-01-01"
    assert params["end_date"] == "2024-01-31"
    assert params["hourly"].split(",") == open_meteo.VARIABLES
    assert params["timezone"] == "GMT"
    assert params["wind_speed_unit"] == "ms"
    assert faux_get.call_args.kwargs["timeout"] > 0


def test_recuperer_meteo_propage_les_erreurs_http(monkeypatch):
    reponse = MagicMock()
    reponse.raise_for_status.side_effect = requests.HTTPError("503")
    monkeypatch.setattr(open_meteo.requests, "get", MagicMock(return_value=reponse))

    with pytest.raises(requests.HTTPError):
        open_meteo.recuperer_meteo(3.3, 50.4, "2024-01-01", "2024-01-31")


# --- lire_departement ---


def faux_catalogue_departements(lignes):
    catalogue = MagicMock()
    table = catalogue.load_table.return_value
    table.scan.return_value.to_arrow.return_value.to_pylist.return_value = lignes
    return catalogue


def test_lire_departement_filtre_sur_le_code(monkeypatch):
    ligne = {"code_departement": "59", "longitude": 3.26, "latitude": 50.42}
    catalogue = faux_catalogue_departements([ligne])
    monkeypatch.setattr(open_meteo, "charger_catalogue", lambda: catalogue)

    assert open_meteo.lire_departement("59") == ligne
    catalogue.load_table.assert_called_once_with("bronze.ref_departements")
    filtre = catalogue.load_table.return_value.scan.call_args.kwargs["row_filter"]
    assert filtre.term.name == "code_departement"
    assert filtre.literal.value == "59"


def test_lire_departement_inconnu(monkeypatch):
    catalogue = faux_catalogue_departements([])
    monkeypatch.setattr(open_meteo, "charger_catalogue", lambda: catalogue)

    with pytest.raises(ValueError, match="Département inconnu : 999"):
        open_meteo.lire_departement("999")


# --- ecrire_table ---


def lignes_valides(nb):
    return [
        {
            "code_departement": "59",
            "horodatage": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "temperature_2m": 7.5,
            "wind_speed_100m": 13.93,
            "shortwave_radiation": 0.0,
            "precipitation": 0.7,
            "snowfall": 0.0,
            "snow_depth": 0.0,
            "longitude_grille": 3.3,
            "latitude_grille": 50.4,
            "altitude": 17.0,
            "date_extraction": date(2026, 1, 1),
        }
    ] * nb


@pytest.mark.parametrize("nb", [0, 743, 745])
def test_ecrire_table_refuse_un_nombre_de_lignes_incorrect(
    monkeypatch, periode_janvier, nb
):
    charger = MagicMock(side_effect=AssertionError("catalogue appelé"))
    monkeypatch.setattr(open_meteo, "charger_catalogue", charger)

    with pytest.raises(ValueError, match=f"{nb} lignes au lieu de 744"):
        open_meteo.ecrire_table(lignes_valides(nb))

    charger.assert_not_called()


def preparer_catalogue(monkeypatch, partitions):
    catalogue = MagicMock()
    table = catalogue.create_table_if_not_exists.return_value
    table.spec.return_value.fields = partitions
    monkeypatch.setattr(open_meteo, "charger_catalogue", lambda: catalogue)
    return catalogue, table


def test_ecrire_table_partitionne_par_mois_une_table_sans_partition(
    monkeypatch, periode_janvier
):
    catalogue, table = preparer_catalogue(monkeypatch, partitions=[])

    open_meteo.ecrire_table(lignes_valides(744))

    catalogue.create_namespace_if_not_exists.assert_called_once_with("bronze")
    assert catalogue.create_table_if_not_exists.call_args.args[0] == (
        "bronze.meteo_horaire"
    )
    evolution = table.update_spec.return_value.__enter__.return_value
    colonne, transformation, nom = evolution.add_field.call_args.args
    assert colonne == "horodatage"
    assert isinstance(transformation, MonthTransform)
    assert nom == "horodatage_month"
    assert table.overwrite.call_args.args[0].num_rows == 744


def test_ecrire_table_ne_repartitionne_pas_une_table_deja_partitionnee(
    monkeypatch, periode_janvier
):
    _, table = preparer_catalogue(monkeypatch, partitions=["horodatage_month"])

    open_meteo.ecrire_table(lignes_valides(744))

    table.update_spec.assert_not_called()
    table.overwrite.assert_called_once()
