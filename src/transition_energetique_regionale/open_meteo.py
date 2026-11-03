from datetime import date, datetime, timezone

import pyarrow as pa
import requests
from dotenv import load_dotenv
from pyiceberg.expressions import EqualTo
from pyiceberg.transforms import MonthTransform

from transition_energetique_regionale.catalogue import charger_catalogue

API_METEO = "https://archive-api.open-meteo.com/v1/archive"

VARIABLES = [
    "temperature_2m",
    "wind_speed_100m",
    "shortwave_radiation",
    "precipitation",
    "snowfall",
    "snow_depth",
]

# pour le test, on ne récupère qu'un département pour limiter le nombre de lignes
NB_DEPARTEMENTS = 1

PERIODE = {
    "debut": "2024-01-01",
    "fin": "2024-01-31",
}


# Schéma de la table bronze.meteo_horaire
SCHEMA = pa.schema(
    [
        ("code_departement", pa.string()),
        ("horodatage", pa.timestamp("us", tz="UTC")),
        ("temperature_2m", pa.float64()),  # °C
        ("wind_speed_100m", pa.float64()),  # m/s
        ("shortwave_radiation", pa.float64()),  # W/m²
        ("precipitation", pa.float64()),  # mm
        ("snowfall", pa.float64()),  # cm
        ("snow_depth", pa.float64()),  # m
        ("longitude_grille", pa.float64()),
        ("latitude_grille", pa.float64()),
        ("altitude", pa.float64()),
        ("date_extraction", pa.date32()),
    ]
)


def recuperer_meteo(longitude: float, latitude: float, debut: str, fin: str) -> dict:
    """Récupère les données météo horaires pour un département donné par sa longitude et latitude.

    Args:
        longitude (float): La longitude du département (calculée dans calculer_centre_et_population).
        latitude (float): La latitude du département.
        debut (str): La date de début de la période.
        fin (str): La date de fin de la période.

    Returns:
        dict: Un dictionnaire contenant les données météo horaires.
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": debut,
        "end_date": fin,
        "hourly": ",".join(VARIABLES),
        "timezone": "GMT",
        "wind_speed_unit": "ms",
    }
    response = requests.get(API_METEO, params=params, timeout=60)
    response.raise_for_status()
    return response.json()


def lire_departement(code) -> dict:
    """Lit la ligne du département dans bronze.ref_departements.

    Args:
        code (str): Le code du département.

    Returns:
        dict: Un dictionnaire contenant les données du département.
    """
    catalogue = charger_catalogue()
    table = catalogue.load_table("bronze.ref_departements")
    departement = (
        table.scan(
            row_filter=EqualTo("code_departement", code),
            selected_fields=("code_departement", "longitude", "latitude"),
        )
        .to_arrow()
        .to_pylist()
    )
    if not departement:
        raise ValueError(f"Département inconnu : {code}")
    return departement[0]


def transformer_reponse(code_departement, reponse) -> list[dict]:
    """Enrichit la réponse de l'API météo avec les données du département.

    Args:
        code_departement (str): Le code du département.
        reponse (dict): La réponse de l'API météo.

    Returns:
        list: Une liste de dictionnaires contenant les données météo horaires par département.
    """
    donnees = []
    for i in range(len(reponse["hourly"]["time"])):
        horodatage = datetime.fromisoformat(reponse["hourly"]["time"][i]).replace(
            tzinfo=timezone.utc
        )
        donnees.append(
            {
                "code_departement": code_departement,
                "horodatage": horodatage,
                "temperature_2m": reponse["hourly"]["temperature_2m"][i],
                "wind_speed_100m": reponse["hourly"]["wind_speed_100m"][i],
                "shortwave_radiation": reponse["hourly"]["shortwave_radiation"][i],
                "precipitation": reponse["hourly"]["precipitation"][i],
                "snowfall": reponse["hourly"]["snowfall"][i],
                "snow_depth": reponse["hourly"]["snow_depth"][i],
                "longitude_grille": reponse["longitude"],
                "latitude_grille": reponse["latitude"],
                "altitude": reponse["elevation"],
                "date_extraction": date.today(),
            }
        )
    return donnees


def nb_lignes_attendues(nb_departements: int, debut: str, fin: str) -> int:
    """Calcule le nombre de lignes attendues dans la table bronze.meteo_horaire.
    Sert de référence pour vérifier que la totalité des lignes a été récupérée.
    Les années bisextiles sont prises en compte dans le calcul du nombre de jours.
    Les changements d'heure ne sont pas pris en compte, car l'API renvoie toujours 24 heures par jour.

    Returns:
        int: Le nombre de lignes attendues.
    """
    nb_jours = (date.fromisoformat(fin) - date.fromisoformat(debut)).days + 1
    return nb_departements * nb_jours * 24


def ecrire_table(lignes: list[dict]) -> None:
    """Écrit les lignes dans bronze.meteo_horaire, en remplaçant son contenu.

    Args:
        lignes (list): Une liste de dictionnaires contenant les données météo horaires.
    """

    # Vérification que la totalité des lignes correspond au nombre attendu de départements * nombre de jours * 24 heures
    attendu = nb_lignes_attendues(NB_DEPARTEMENTS, PERIODE["debut"], PERIODE["fin"])
    if len(lignes) != attendu:
        raise ValueError(f"{len(lignes)} lignes au lieu de {attendu}")

    donnees = pa.Table.from_pylist(lignes, schema=SCHEMA)

    catalogue = charger_catalogue()
    catalogue.create_namespace_if_not_exists("bronze")
    table = catalogue.create_table_if_not_exists("bronze.meteo_horaire", schema=SCHEMA)

    if not table.spec().fields:
        with table.update_spec() as evolution:
            evolution.add_field("horodatage", MonthTransform(), "horodatage_month")

    table.overwrite(donnees)


if __name__ == "__main__":
    load_dotenv()

    code_departement = "59"
    dept = lire_departement(code_departement)

    data = recuperer_meteo(
        longitude=dept["longitude"],
        latitude=dept["latitude"],
        debut=PERIODE["debut"],
        fin=PERIODE["fin"],
    )

    transformed_data = transformer_reponse(code_departement, data)

    ecrire_table(transformed_data)
