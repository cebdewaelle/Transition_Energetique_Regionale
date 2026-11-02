import pytest

from transition_energetique_regionale.departements import (
    calculer_centre_et_population,
)


def test_calculer_centre_et_population():
    communes = [
        {"population": 100, "centre": {"coordinates": [2.0, 50.0]}},
        {"population": 300, "centre": {"coordinates": [4.0, 48.0]}},
    ]

    resultat = calculer_centre_et_population(communes)

    assert resultat == {"longitude": 3.0, "latitude": 49.0, "population": 400}


def test_calculer_centre_et_population_sans_commune():
    with pytest.raises(ValueError, match="Aucune commune"):
        calculer_centre_et_population([])
