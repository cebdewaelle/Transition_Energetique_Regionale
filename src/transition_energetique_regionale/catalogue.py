import os

from pyiceberg.catalog import Catalog, load_catalog


def charger_catalogue() -> Catalog:
    """Charge le catalogue Polaris à partir des variables d'environnement.

    Returns:
        Catalog: Le catalogue Polaris chargé.
    """
    return load_catalog(
        "polaris",
        **{
            "type": "rest",
            "uri": os.environ["POLARIS_URI"],
            "warehouse": os.environ["CATALOG_NAME"],
            "credential": f"{os.environ['POLARIS_ADMIN_CLIENT_ID']}:{os.environ['POLARIS_ADMIN_CREDENTIALS']}",
            "scope": "PRINCIPAL_ROLE:ALL",
        },
    )
