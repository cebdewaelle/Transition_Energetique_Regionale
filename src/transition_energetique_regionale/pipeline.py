import subprocess
from pathlib import Path

from dotenv import load_dotenv
from prefect import flow, get_run_logger, task
from datetime import date, timedelta
from transition_energetique_regionale.open_meteo import ingerer_periode

DOSSIER_DBT = Path(__file__).resolve().parents[2] / "dbt"


@task(retries=2, retry_delay_seconds=300)
def ingerer(debut: str, fin: str) -> None:
    ingerer_periode(debut, fin)


@task
def lancer_dbt(commande: str) -> None:
    resultat = subprocess.run(
        ["dbt", commande], cwd=DOSSIER_DBT, capture_output=True, text=True
    )
    get_run_logger().info(resultat.stdout)
    if resultat.returncode != 0:
        get_run_logger().error(resultat.stderr)
        raise RuntimeError(f"dbt {commande} a échoué")


@flow(name="pipeline-meteo", log_prints=True)
def pipeline_meteo(debut: str | None = None, fin: str | None = None) -> None:
    if debut is None or fin is None:
        today = date.today()
        debut, fin = mois_precedent(today)

    if date.fromisoformat(fin) >= date.today():
        raise ValueError(f"La fin de période doit être passée : {fin}")

    get_run_logger().info(f"Exécution du pipeline du : {debut} au {fin}")

    ingerer(debut, fin)
    lancer_dbt("run")
    lancer_dbt("test")


def mois_precedent(date_ref: date) -> tuple[str, str]:
    first_day_of_current_month = date_ref.replace(day=1)
    last_day_of_previous_month = first_day_of_current_month - timedelta(days=1)
    first_day_of_previous_month = last_day_of_previous_month.replace(day=1)

    return (
        first_day_of_previous_month.strftime("%Y-%m-%d"),
        last_day_of_previous_month.strftime("%Y-%m-%d"),
    )


if __name__ == "__main__":
    load_dotenv()
    pipeline_meteo.serve(name="mensuel", cron="0 6 10 * *")
