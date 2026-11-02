from datetime import date

import pyarrow as pa
import requests
from dotenv import load_dotenv

from transition_energetique_regionale.catalogue import charger_catalogue

API_GEO = "https://geo.api.gouv.fr"
NB_DEPARTEMENTS = 94

# Les 12 régions couvertes par les données éCO2mix (la Corse n'y figure pas).
CODES_REGIONS = {
    "11": "Île-de-France",
    "24": "Centre-Val de Loire",
    "27": "Bourgogne-Franche-Comté",
    "28": "Normandie",
    "32": "Hauts-de-France",
    "44": "Grand Est",
    "52": "Pays de la Loire",
    "53": "Bretagne",
    "75": "Nouvelle-Aquitaine",
    "76": "Occitanie",
    "84": "Auvergne-Rhône-Alpes",
    "93": "Provence-Alpes-Côte d'Azur",
}

# Schéma de la table bronze.ref_departements
SCHEMA = pa.schema(
    [
        ("code_departement", pa.string()),
        ("nom", pa.string()),
        ("code_region", pa.string()),
        ("longitude", pa.float64()),
        ("latitude", pa.float64()),
        ("population", pa.int64()),
        ("date_extraction", pa.date32()),
    ]
)


def calculer_centre_et_population(communes: list[dict]) -> dict[str, float | int]:
    """Calcule la moyenne des centres des communes et la population totale d'un département.

    Args:
        communes (list): Une liste de communes, au format de l'API Géo.

    Returns:
        dict: La longitude, la latitude et la population totale.
    """
    if not communes:
        raise ValueError("Aucune commune reçue")

    population_totale = sum(commune["population"] for commune in communes)
    longitude_centre = sum(
        commune["centre"]["coordinates"][0] for commune in communes
    ) / len(communes)
    latitude_centre = sum(
        commune["centre"]["coordinates"][1] for commune in communes
    ) / len(communes)

    return {
        "longitude": longitude_centre,
        "latitude": latitude_centre,
        "population": population_totale,
    }


def _get_json(chemin: str, params: dict | None = None) -> list[dict]:
    """Interroge l'API Géo et renvoie sa réponse, ou lève une erreur en cas d'échec.

    Args:
        chemin (str): Le chemin de la ressource, par exemple /regions/28/departements.
        params (dict): Les paramètres de la requête.

    Returns:
        list: La réponse de l'API.
    """
    reponse = requests.get(f"{API_GEO}{chemin}", params=params, timeout=30)
    reponse.raise_for_status()
    return reponse.json()


def recuperer_departements() -> list[dict]:
    """Interroge l'API et construit les 94 lignes des départements de métropole.

    Returns:
        list: Une liste de dictionnaires contenant les informations des départements.
    """
    liste_departements = []
    date_extraction = date.today()

    for code_region in CODES_REGIONS:
        for departement in _get_json(f"/regions/{code_region}/departements"):
            communes = _get_json(
                f"/departements/{departement['code']}/communes",
                params={"fields": "population,centre"},
            )
            centre_et_population = calculer_centre_et_population(communes)

            liste_departements.append(
                {
                    "code_departement": departement["code"],
                    "nom": departement["nom"],
                    "code_region": code_region,
                    "longitude": centre_et_population["longitude"],
                    "latitude": centre_et_population["latitude"],
                    "population": centre_et_population["population"],
                    "date_extraction": date_extraction,
                }
            )
    return liste_departements


def ecrire_table(liste_departements: list[dict]) -> None:
    """Écrit les lignes dans bronze.ref_departements, en remplaçant son contenu.

    Args:
        liste_departements (list): Une liste de dictionnaires contenant les informations des départements.
    """
    if len(liste_departements) != NB_DEPARTEMENTS:
        raise ValueError(
            f"{len(liste_departements)} départements au lieu de {NB_DEPARTEMENTS}"
        )

    donnees = pa.Table.from_pylist(liste_departements, schema=SCHEMA)

    catalogue = charger_catalogue()
    catalogue.create_namespace_if_not_exists("bronze")
    table = catalogue.create_table_if_not_exists(
        "bronze.ref_departements", schema=SCHEMA
    )

    table.overwrite(donnees)


if __name__ == "__main__":
    load_dotenv()

    liste_departements = recuperer_departements()
    ecrire_table(liste_departements)
    print(f"{len(liste_departements)} départements écrits dans bronze.ref_departements")
