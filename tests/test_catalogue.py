import pytest

from transition_energetique_regionale import catalogue


@pytest.fixture
def variables_polaris(monkeypatch):
    monkeypatch.setenv("POLARIS_URI", "http://polaris.test/api/catalog")
    monkeypatch.setenv("CATALOG_NAME", "catalogue_test")
    monkeypatch.setenv("POLARIS_ADMIN_CLIENT_ID", "identifiant")
    monkeypatch.setenv("POLARIS_ADMIN_CREDENTIALS", "secret")


def test_charger_catalogue_transmet_la_configuration(monkeypatch, variables_polaris):
    appels = {}

    def faux_load_catalog(nom, **proprietes):
        appels["nom"] = nom
        appels["proprietes"] = proprietes
        return "catalogue"

    monkeypatch.setattr(catalogue, "load_catalog", faux_load_catalog)

    assert catalogue.charger_catalogue() == "catalogue"
    assert appels["nom"] == "polaris"
    assert appels["proprietes"] == {
        "type": "rest",
        "uri": "http://polaris.test/api/catalog",
        "warehouse": "catalogue_test",
        "credential": "identifiant:secret",
        "scope": "PRINCIPAL_ROLE:ALL",
    }


@pytest.mark.parametrize(
    "variable",
    [
        "POLARIS_URI",
        "CATALOG_NAME",
        "POLARIS_ADMIN_CLIENT_ID",
        "POLARIS_ADMIN_CREDENTIALS",
    ],
)
def test_charger_catalogue_exige_chaque_variable(
    monkeypatch, variables_polaris, variable
):
    monkeypatch.delenv(variable)

    with pytest.raises(KeyError, match=variable):
        catalogue.charger_catalogue()
