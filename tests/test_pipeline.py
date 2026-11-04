from datetime import date
from unittest.mock import MagicMock

import pytest

from transition_energetique_regionale import pipeline


@pytest.mark.parametrize(
    ("aujourdhui", "attendu"),
    [
        pytest.param(date(2026, 11, 4), ("2026-10-01", "2026-10-31"), id="courant"),
        pytest.param(date(2026, 1, 15), ("2025-12-01", "2025-12-31"), id="janvier"),
        pytest.param(date(2024, 3, 1), ("2024-02-01", "2024-02-29"), id="bissextile"),
        pytest.param(date(2025, 3, 31), ("2025-02-01", "2025-02-28"), id="fin_de_mois"),
    ],
)
def test_mois_precedent(aujourdhui, attendu):
    assert pipeline.mois_precedent(aujourdhui) == attendu


@pytest.fixture
def etapes(monkeypatch):
    """Remplace les tâches et mémorise l'ordre des appels, sans serveur Prefect."""
    appels = []
    monkeypatch.setattr(pipeline, "get_run_logger", MagicMock())
    monkeypatch.setattr(
        pipeline, "ingerer", lambda debut, fin: appels.append(("ingerer", debut, fin))
    )
    monkeypatch.setattr(
        pipeline, "lancer_dbt", lambda commande: appels.append(("dbt", commande))
    )
    return appels


def test_le_flow_enchaine_ingestion_run_et_test(etapes):
    pipeline.pipeline_meteo.fn("2024-01-01", "2024-01-31")

    assert etapes == [
        ("ingerer", "2024-01-01", "2024-01-31"),
        ("dbt", "run"),
        ("dbt", "test"),
    ]


def test_le_flow_prend_le_mois_precedent_par_defaut(monkeypatch, etapes):
    monkeypatch.setattr(
        pipeline, "mois_precedent", lambda _: ("2026-10-01", "2026-10-31")
    )

    pipeline.pipeline_meteo.fn()

    assert etapes[0] == ("ingerer", "2026-10-01", "2026-10-31")


def test_le_flow_s_arrete_si_l_ingestion_echoue(monkeypatch, etapes):
    def echec(debut, fin):
        raise RuntimeError("panne API")

    monkeypatch.setattr(pipeline, "ingerer", echec)

    with pytest.raises(RuntimeError, match="panne API"):
        pipeline.pipeline_meteo.fn("2024-01-01", "2024-01-31")

    assert etapes == []


@pytest.mark.parametrize(
    ("debut", "fin"),
    [
        pytest.param("2999-01-01", "2999-01-31", id="futur"),
        pytest.param(date.today().isoformat(), date.today().isoformat(), id="aujourdhui"),
    ],
)
def test_le_flow_refuse_une_fin_de_periode_non_passee(etapes, debut, fin):
    with pytest.raises(ValueError, match="doit être passée"):
        pipeline.pipeline_meteo.fn(debut, fin)

    assert etapes == []


def preparer_dbt(monkeypatch, code_retour):
    resultat = MagicMock(returncode=code_retour, stdout="sortie dbt")
    executer = MagicMock(return_value=resultat)
    journal = MagicMock()
    monkeypatch.setattr(pipeline.subprocess, "run", executer)
    monkeypatch.setattr(pipeline, "get_run_logger", lambda: journal)
    return executer, journal


def test_lancer_dbt_s_execute_dans_le_dossier_dbt(monkeypatch):
    executer, journal = preparer_dbt(monkeypatch, code_retour=0)

    pipeline.lancer_dbt.fn("run")

    assert executer.call_args.args[0] == ["dbt", "run"]
    assert executer.call_args.kwargs["cwd"] == pipeline.DOSSIER_DBT
    assert (pipeline.DOSSIER_DBT / "dbt_project.yml").is_file()
    journal.info.assert_called_once_with("sortie dbt")


def test_lancer_dbt_echoue_si_dbt_echoue(monkeypatch):
    preparer_dbt(monkeypatch, code_retour=1)

    with pytest.raises(RuntimeError, match="dbt test a échoué"):
        pipeline.lancer_dbt.fn("test")


def test_ingerer_appelle_ingerer_periode(monkeypatch):
    ingerer_periode = MagicMock()
    monkeypatch.setattr(pipeline, "ingerer_periode", ingerer_periode)

    pipeline.ingerer.fn("2024-01-01", "2024-01-31")

    ingerer_periode.assert_called_once_with("2024-01-01", "2024-01-31")


def test_l_ingestion_est_reessayee():
    assert pipeline.ingerer.retries == 2
    assert pipeline.ingerer.retry_delay_seconds == 300
