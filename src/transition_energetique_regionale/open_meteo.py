import time
from datetime import date, datetime, timedelta, timezone

import pyarrow as pa
import requests
from dotenv import load_dotenv
from pyiceberg.expressions import And, EqualTo, GreaterThanOrEqual, LessThan
from pyiceberg.table import Table
from pyiceberg.transforms import MonthTransform
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

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

NB_DEPARTEMENTS = 94

# Une requête d'un mois compte pour environ 2,2 appels (limite : 600 par minute).
PAUSE_ENTRE_APPELS = 1.0

PERIODE = {
    "debut": "2024-01-01",
    "fin": "2025-12-31",
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


def creer_session() -> requests.Session:
    """Crée la session HTTP, qui réessaie en cas de limite d'appels ou d'erreur serveur.

    Returns:
        requests.Session: La session à réutiliser pour tous les appels.
    """
    session = requests.Session()
    reessais = Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    session.mount("https://", HTTPAdapter(max_retries=reessais))
    return session


def recuperer_meteo(
    session: requests.Session, longitude: float, latitude: float, debut: str, fin: str
) -> dict:
    """Récupère les données météo horaires pour un département donné par sa longitude et latitude.

    Args:
        session (requests.Session): La session HTTP à utiliser.
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
    response = session.get(API_METEO, params=params, timeout=60)
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


def lire_departements() -> list[dict]:
    """Lit toutes les lignes des départements dans bronze.ref_departements.

    Returns:
        list: Une liste de dictionnaires contenant les données des départements.
    """
    catalogue = charger_catalogue()
    table = catalogue.load_table("bronze.ref_departements")
    return (
        table.scan(selected_fields=("code_departement", "longitude", "latitude"))
        .to_arrow()
        .to_pylist()
    )


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


def ouvrir_table() -> Table:
    """Ouvre bronze.meteo_horaire, en la créant et en la partitionnant par mois si besoin.

    Returns:
        Table: La table Iceberg.
    """
    catalogue = charger_catalogue()
    catalogue.create_namespace_if_not_exists("bronze")
    table = catalogue.create_table_if_not_exists("bronze.meteo_horaire", schema=SCHEMA)

    if not table.spec().fields:
        with table.update_spec() as evolution:
            evolution.add_field("horodatage", MonthTransform(), "horodatage_month")

    return table


def ecrire_mois(table: Table, lignes: list[dict], debut: str, fin: str) -> None:
    """Remplace les lignes d'un mois dans bronze.meteo_horaire, sans toucher aux autres mois.

    Args:
        table (Table): La table Iceberg.
        lignes (list): Une liste de dictionnaires contenant les données météo horaires.
        debut (str): Le premier jour du mois.
        fin (str): Le dernier jour du mois.
    """
    # Vérification que la totalité des lignes correspond au nombre attendu de départements * nombre de jours * 24 heures
    attendu = nb_lignes_attendues(NB_DEPARTEMENTS, debut, fin)
    if len(lignes) != attendu:
        raise ValueError(f"{len(lignes)} lignes au lieu de {attendu}")

    donnees = pa.Table.from_pylist(lignes, schema=SCHEMA)

    debut_utc = datetime.fromisoformat(debut).replace(tzinfo=timezone.utc)
    fin_utc = datetime.fromisoformat(fin).replace(tzinfo=timezone.utc)
    filtre = And(
        GreaterThanOrEqual("horodatage", debut_utc),
        LessThan("horodatage", fin_utc + timedelta(days=1)),
    )

    table.overwrite(donnees, overwrite_filter=filtre)


def numero_partition(jour: str) -> int:
    """Calcule le numéro de partition d'une date, soit le nombre de mois depuis janvier 1970.

    Args:
        jour (str): Une date du mois.

    Returns:
        int: Le numéro de la partition.
    """
    d = date.fromisoformat(jour)
    return (d.year - 1970) * 12 + d.month - 1


def lignes_par_partition(table: Table) -> dict[int, int]:
    """Lit le nombre de lignes de chaque partition, sans lire les données.

    Args:
        table (Table): La table Iceberg.

    Returns:
        dict: Le nombre de lignes par numéro de partition.
    """
    # inspect.partitions() lève une erreur sur une table encore jamais écrite.
    if table.current_snapshot() is None:
        return {}

    return {
        ligne["partition"]["horodatage_month"]: ligne["record_count"]
        for ligne in table.inspect.partitions().to_pylist()
    }


def decouper_en_mois(debut: str, fin: str) -> list[tuple[str, str]]:
    """Découpe une période donnée en sous-périodes mensuelles.

    Args:
        debut (str): La date de début de la période.
        fin (str): La date de fin de la période.

    Returns:
        list: Une liste de tuples contenant les dates de début et de fin des sous-périodes mensuelles.
    """
    debut_dt = datetime.fromisoformat(debut)
    fin_dt = datetime.fromisoformat(fin)

    mois = []
    while debut_dt <= fin_dt:
        fin_mois = (
            datetime(debut_dt.year, debut_dt.month + 1, 1) - timedelta(days=1)
            if debut_dt.month < 12
            else datetime(debut_dt.year + 1, 1, 1) - timedelta(days=1)
        )
        # On ne dépasse pas la date de fin de la période
        fin_mois = min(fin_mois, fin_dt)

        mois.append((debut_dt.date().isoformat(), fin_mois.date().isoformat()))
        # On passe au mois suivant
        debut_dt = fin_mois + timedelta(days=1)

    return mois


def ingerer_periode(debut: str, fin: str) -> None:
    """Récupère les données météo horaires de tous les départements, mois par mois,
    puis les écrit dans bronze.meteo_horaire. Les mois déjà complets sont sautés :
    le script peut donc être relancé après une interruption.

    Args:
        debut (str): La date de début de la période.
        fin (str): La date de fin de la période.
    """
    departements = lire_departements()
    if len(departements) != NB_DEPARTEMENTS:
        raise ValueError(
            f"{len(departements)} départements au lieu de {NB_DEPARTEMENTS}"
        )

    table = ouvrir_table()
    deja_ecrit = lignes_par_partition(table)
    session = creer_session()

    for debut_mois, fin_mois in decouper_en_mois(debut, fin):
        attendu = nb_lignes_attendues(NB_DEPARTEMENTS, debut_mois, fin_mois)
        if deja_ecrit.get(numero_partition(debut_mois)) == attendu:
            print(f"{debut_mois[:7]} : déjà complet", flush=True)
            continue

        lignes = []
        for departement in departements:
            reponse = recuperer_meteo(
                session,
                longitude=departement["longitude"],
                latitude=departement["latitude"],
                debut=debut_mois,
                fin=fin_mois,
            )
            lignes.extend(transformer_reponse(departement["code_departement"], reponse))
            time.sleep(PAUSE_ENTRE_APPELS)

        ecrire_mois(ouvrir_table(), lignes, debut_mois, fin_mois)
        print(f"{debut_mois[:7]} : {len(lignes)} lignes écrites", flush=True)


if __name__ == "__main__":
    load_dotenv()

    ingerer_periode(PERIODE["debut"], PERIODE["fin"])
