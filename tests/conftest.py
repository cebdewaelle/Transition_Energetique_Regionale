import pytest
import requests


@pytest.fixture(autouse=True)
def bloquer_reseau(monkeypatch):
    """Fait échouer tout test qui tenterait un vrai appel HTTP."""

    def appel_interdit(*args, **kwargs):
        raise AssertionError("Appel réseau interdit dans les tests unitaires")

    monkeypatch.setattr(requests.sessions.Session, "request", appel_interdit)
