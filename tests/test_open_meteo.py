from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock

import pyarrow as pa
import pytest
import requests
from pyiceberg.expressions import GreaterThanOrEqual, LessThan
from pyiceberg.expressions.literals import literal
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


# --- creer_session et recuperer_meteo ---


def test_recuperer_meteo_envoie_les_bons_parametres():
    session = MagicMock()
    session.get.return_value.json.return_value = {"hourly": {}}

    resultat = open_meteo.recuperer_meteo(
        session, 3.3, 50.4, "2024-01-01", "2024-01-31"
    )

    assert resultat == {"hourly": {}}
    assert session.get.call_args.args[0] == open_meteo.API_METEO
    params = session.get.call_args.kwargs["params"]
    assert params["longitude"] == 3.3
    assert params["latitude"] == 50.4
    assert params["start_date"] == "2024-01-01"
    assert params["end_date"] == "2024-01-31"
    assert params["hourly"].split(",") == open_meteo.VARIABLES
    assert params["timezone"] == "GMT"
    assert params["wind_speed_unit"] == "ms"
    assert session.get.call_args.kwargs["timeout"] > 0


def test_recuperer_meteo_propage_les_erreurs_http():
    session = MagicMock()
    session.get.return_value.raise_for_status.side_effect = requests.HTTPError("503")

    with pytest.raises(requests.HTTPError):
        open_meteo.recuperer_meteo(session, 3.3, 50.4, "2024-01-01", "2024-01-31")


def test_la_session_reessaie_les_erreurs_temporaires():
    reessais = (
        open_meteo.creer_session().get_adapter("https://exemple.test").max_retries
    )

    assert reessais.total == 5
    assert reessais.backoff_factor == 2
    assert {429, 500, 502, 503, 504} == set(reessais.status_forcelist)
    assert set(reessais.allowed_methods) == {"GET"}


# --- decouper_en_mois ---


@pytest.mark.parametrize(
    ("debut", "fin", "attendu"),
    [
        pytest.param(
            "2024-01-01", "2024-01-31", [("2024-01-01", "2024-01-31")], id="un_mois"
        ),
        pytest.param(
            "2024-02-01", "2024-02-29", [("2024-02-01", "2024-02-29")], id="bissextile"
        ),
        pytest.param(
            "2025-02-01", "2025-02-28", [("2025-02-01", "2025-02-28")], id="non_bissextile"
        ),
        pytest.param(
            "2024-12-01",
            "2025-01-31",
            [("2024-12-01", "2024-12-31"), ("2025-01-01", "2025-01-31")],
            id="changement_annee",
        ),
        pytest.param(
            "2024-01-15", "2024-01-20", [("2024-01-15", "2024-01-20")], id="dans_un_mois"
        ),
        pytest.param(
            "2024-01-15",
            "2024-02-10",
            [("2024-01-15", "2024-01-31"), ("2024-02-01", "2024-02-10")],
            id="mois_partiels",
        ),
        pytest.param("2024-02-01", "2024-01-01", [], id="periode_inversee"),
    ],
)
def test_decouper_en_mois(debut, fin, attendu):
    assert open_meteo.decouper_en_mois(debut, fin) == attendu


def test_decouper_2024_2025_couvre_chaque_jour_une_seule_fois():
    mois = open_meteo.decouper_en_mois("2024-01-01", "2025-12-31")

    assert len(mois) == 24
    assert mois[0][0] == "2024-01-01"
    assert mois[-1][1] == "2025-12-31"
    for (_, fin), (debut_suivant, _) in zip(mois, mois[1:]):
        assert date.fromisoformat(debut_suivant) == date.fromisoformat(
            fin
        ) + timedelta(days=1)
    assert sum(open_meteo.nb_lignes_attendues(94, d, f) for d, f in mois) == 1_649_136


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


# --- ouvrir_table ---


def preparer_catalogue(monkeypatch, partitions):
    catalogue = MagicMock()
    table = catalogue.create_table_if_not_exists.return_value
    table.spec.return_value.fields = partitions
    monkeypatch.setattr(open_meteo, "charger_catalogue", lambda: catalogue)
    return catalogue, table


def test_ouvrir_table_partitionne_par_mois_une_table_sans_partition(monkeypatch):
    catalogue, table = preparer_catalogue(monkeypatch, partitions=[])

    assert open_meteo.ouvrir_table() is table

    catalogue.create_namespace_if_not_exists.assert_called_once_with("bronze")
    assert catalogue.create_table_if_not_exists.call_args.args[0] == (
        "bronze.meteo_horaire"
    )
    evolution = table.update_spec.return_value.__enter__.return_value
    colonne, transformation, nom = evolution.add_field.call_args.args
    assert colonne == "horodatage"
    assert isinstance(transformation, MonthTransform)
    assert nom == "horodatage_month"


def test_ouvrir_table_ne_repartitionne_pas_une_table_deja_partitionnee(monkeypatch):
    _, table = preparer_catalogue(monkeypatch, partitions=["horodatage_month"])

    open_meteo.ouvrir_table()

    table.update_spec.assert_not_called()


# --- ecrire_mois ---


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
def test_ecrire_mois_refuse_un_nombre_de_lignes_incorrect(monkeypatch, nb):
    monkeypatch.setattr(open_meteo, "NB_DEPARTEMENTS", 1)
    table = MagicMock()

    with pytest.raises(ValueError, match=f"{nb} lignes au lieu de 744"):
        open_meteo.ecrire_mois(table, lignes_valides(nb), "2024-01-01", "2024-01-31")

    table.overwrite.assert_not_called()


@pytest.mark.parametrize(
    ("debut", "fin", "borne_basse", "borne_haute", "nb"),
    [
        pytest.param(
            "2024-03-01",
            "2024-03-31",
            datetime(2024, 3, 1, tzinfo=timezone.utc),
            datetime(2024, 4, 1, tzinfo=timezone.utc),
            744,
            id="mars",
        ),
        pytest.param(
            "2024-12-01",
            "2024-12-31",
            datetime(2024, 12, 1, tzinfo=timezone.utc),
            datetime(2025, 1, 1, tzinfo=timezone.utc),
            744,
            id="fin_annee",
        ),
    ],
)
def test_ecrire_mois_ne_remplace_que_le_mois_ecrit(
    monkeypatch, debut, fin, borne_basse, borne_haute, nb
):
    monkeypatch.setattr(open_meteo, "NB_DEPARTEMENTS", 1)
    table = MagicMock()

    open_meteo.ecrire_mois(table, lignes_valides(nb), debut, fin)

    assert table.overwrite.call_args.args[0].num_rows == nb
    filtre = table.overwrite.call_args.kwargs["overwrite_filter"]
    assert isinstance(filtre.left, GreaterThanOrEqual)
    assert isinstance(filtre.right, LessThan)
    assert filtre.left.term.name == filtre.right.term.name == "horodatage"
    assert filtre.left.literal == literal(borne_basse)
    assert filtre.right.literal == literal(borne_haute)


# --- reprise ---


@pytest.mark.parametrize(
    ("jour", "numero"),
    [
        ("1970-01-01", 0),
        ("2024-01-31", 648),
        ("2024-12-01", 659),
        ("2025-01-15", 660),
    ],
)
def test_numero_partition(jour: str, numero: int) -> None:
    assert open_meteo.numero_partition(jour) == numero


def test_lignes_par_partition():
    table = MagicMock()
    table.inspect.partitions.return_value.to_pylist.return_value = [
        {"partition": {"horodatage_month": 648}, "record_count": 744},
        {"partition": {"horodatage_month": 649}, "record_count": 696},
    ]

    assert open_meteo.lignes_par_partition(table) == {648: 744, 649: 696}


def test_lignes_par_partition_sur_une_table_jamais_ecrite():
    table = MagicMock()
    table.current_snapshot.return_value = None
    table.inspect.partitions.side_effect = ValueError("aucun snapshot")

    assert open_meteo.lignes_par_partition(table) == {}


# --- ingerer_periode ---


def reponse_pour(debut, fin):
    """Construit une réponse de l'API avec une valeur par heure de la période."""
    heure = datetime.fromisoformat(debut)
    derniere = datetime.fromisoformat(fin) + timedelta(hours=23)
    temps = []
    while heure <= derniere:
        temps.append(heure.strftime("%Y-%m-%dT%H:%M"))
        heure += timedelta(hours=1)
    return {
        "latitude": 50.4,
        "longitude": 3.3,
        "elevation": 17.0,
        "hourly": {
            "time": temps,
            **{variable: [1.0] * len(temps) for variable in open_meteo.VARIABLES},
        },
    }


@pytest.fixture
def ingestion(monkeypatch):
    """Simule l'API, la table et le temps pour 2 départements."""
    departements = [
        {"code_departement": "59", "longitude": 3.3, "latitude": 50.4},
        {"code_departement": "75", "longitude": 2.3, "latitude": 48.9},
    ]
    table = MagicMock()
    table.inspect.partitions.return_value.to_pylist.return_value = []
    appels = []
    pauses = []

    def faux_recuperer(session, longitude, latitude, debut, fin):
        appels.append((longitude, debut, fin))
        return reponse_pour(debut, fin)

    monkeypatch.setattr(open_meteo, "NB_DEPARTEMENTS", 2)
    monkeypatch.setattr(open_meteo, "lire_departements", lambda: departements)
    monkeypatch.setattr(open_meteo, "ouvrir_table", lambda: table)
    monkeypatch.setattr(open_meteo, "recuperer_meteo", faux_recuperer)
    monkeypatch.setattr(open_meteo.time, "sleep", pauses.append)
    return table, appels, pauses


def test_ingerer_ecrit_un_lot_par_mois_avec_tous_les_departements(ingestion):
    table, appels, _ = ingestion

    open_meteo.ingerer_periode("2024-01-01", "2024-02-29")

    assert len(appels) == 4
    assert table.overwrite.call_count == 2
    assert table.overwrite.call_args_list[0].args[0].num_rows == 2 * 744
    assert table.overwrite.call_args_list[1].args[0].num_rows == 2 * 696
    codes = table.overwrite.call_args_list[0].args[0]["code_departement"].to_pylist()
    assert set(codes) == {"59", "75"}


def test_ingerer_rouvre_la_table_avant_chaque_ecriture(monkeypatch, ingestion):
    """Les identifiants fournis par Polaris expirent : chaque écriture doit en obtenir de neufs."""
    table, _, _ = ingestion
    ouvertures = []

    def compter_ouvertures():
        ouvertures.append(table.overwrite.call_count)
        return table

    monkeypatch.setattr(open_meteo, "ouvrir_table", compter_ouvertures)

    open_meteo.ingerer_periode("2024-01-01", "2024-03-31")

    # Une ouverture pour lire l'état initial, puis une avant chacune des 3 écritures.
    assert ouvertures == [0, 0, 1, 2]


def test_ingerer_marque_une_pause_apres_chaque_appel(ingestion):
    _, appels, pauses = ingestion

    open_meteo.ingerer_periode("2024-01-01", "2024-01-31")

    assert pauses == [open_meteo.PAUSE_ENTRE_APPELS] * len(appels)


def test_ingerer_saute_un_mois_complet_sans_appeler_l_api(ingestion):
    table, appels, _ = ingestion
    table.inspect.partitions.return_value.to_pylist.return_value = [
        {"partition": {"horodatage_month": 648}, "record_count": 2 * 744},
    ]

    open_meteo.ingerer_periode("2024-01-01", "2024-02-29")

    assert {debut for _, debut, _ in appels} == {"2024-02-01"}
    assert table.overwrite.call_count == 1


def test_ingerer_remplace_un_mois_incomplet(ingestion):
    table, appels, _ = ingestion
    table.inspect.partitions.return_value.to_pylist.return_value = [
        {"partition": {"horodatage_month": 648}, "record_count": 744},
    ]

    open_meteo.ingerer_periode("2024-01-01", "2024-01-31")

    assert len(appels) == 2
    assert table.overwrite.call_count == 1


def test_ingerer_n_ecrit_rien_du_mois_en_cas_d_erreur_api(monkeypatch, ingestion):
    table, _, _ = ingestion
    resultats = iter([reponse_pour("2024-01-01", "2024-01-31")])

    def recuperer_puis_echouer(session, longitude, latitude, debut, fin):
        try:
            return next(resultats)
        except StopIteration:
            raise requests.HTTPError("503") from None

    monkeypatch.setattr(open_meteo, "recuperer_meteo", recuperer_puis_echouer)

    with pytest.raises(requests.HTTPError):
        open_meteo.ingerer_periode("2024-01-01", "2024-01-31")

    table.overwrite.assert_not_called()


def test_ingerer_refuse_un_referentiel_incomplet(monkeypatch, ingestion):
    table, appels, _ = ingestion
    monkeypatch.setattr(open_meteo, "lire_departements", lambda: [])

    with pytest.raises(ValueError, match="0 départements au lieu de 2"):
        open_meteo.ingerer_periode("2024-01-01", "2024-01-31")

    assert appels == []
    table.overwrite.assert_not_called()
