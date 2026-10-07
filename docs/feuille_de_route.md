# Feuille de route

Ordre de construction du projet et outils utilisés. Le détail de
l'avancement (difficultés rencontrées, décisions prises) est consigné dans
`JOURNAL.md`.

## Principe

Je construis d'abord un flux complet de bout en bout sur une seule source
de données simple (Open-Meteo), avant d'étendre aux autres sources (Enedis,
ODRE) et aux indicateurs. Chaque brique est validée manuellement avant
d'être orchestrée.

## Environnement de travail

Je travaille sur deux machines : un portable sous Linux et un PC fixe sous
Windows avec WSL2 (Ubuntu 24.04). Le dépôt Git est le seul lien entre les
deux : les volumes Docker restent locaux à chaque machine et sont
reconstruits par le pipeline.

### Outils système

- [x] **Docker + Docker Compose** : moteur Docker natif (Docker 29.8.1,
      Compose v5.5.1 installé via apt). Docker Desktop désinstallé du PC
      fixe pour avoir la même configuration sur les deux machines.
- [x] **Python 3.12.3**
- [x] **uv 0.12.19** : gestion de l'environnement Python et des
      dépendances (`pyproject.toml`, `uv.lock`).
- [x] **Git + GitHub** : branches `main` / `develop` / `feature/*`,
      commits conventionnels vérifiés par commitizen (hook pre-commit
      `commit-msg`), CI GitHub Actions (`.github/workflows/ci.yml`).

### Outils en ligne de commande

- [x] **jq** : lecture et filtrage des réponses JSON des API.
- [x] **AWS CLI 2.37.9** : client S3 pour inspecter RustFS, avec un profil
      `rustfs` (`endpoint_url` sur `http://localhost:9000`,
      `s3.addressing_style` en `path`). J'ai écarté le client `rc` de
      RustFS : redondant avec AWS CLI, et encore en version 0.1.x.
- [x] **DuckDB 1.5.6** : lecture des tables Iceberg en dehors de
      ClickHouse, notamment pour le time travel.
- [x] **clickhouse-client** : pas d'installation locale. J'utilise le
      client inclus dans l'image du serveur
      (`docker compose exec clickhouse clickhouse-client`), toujours à la
      même version que le serveur.

La console web de RustFS est accessible sur
`http://localhost:9001/rustfs/console/`.

### Dépendances Python

Déjà dans le projet (développement) : `pytest`, `commitizen`, `pre-commit`.

Ajoutées au fil des étapes :

- `pyiceberg` : écriture et lecture des tables Iceberg via le catalogue
  Polaris
- `requests` : appels aux API Open-Meteo et ODRE
- `prefect` : orchestration
- `dbt-core` + `dbt-clickhouse` : transformations Silver et Gold
- `clickhouse-connect` : client Python ClickHouse, en dehors de dbt
- `boto3` : accès direct à RustFS, si nécessaire

## Étapes

1. ✅ **Structure du dépôt** (2026-09-27) : projet `uv` en src layout
   (`src/`, `tests/`), dossier `docker/` pour les scripts des services.

2. ✅ **Stockage et catalogue** (2026-09-28) : RustFS et Polaris dans
   `docker-compose.yml`, à partir du guide officiel Polaris/RustFS, avec la
   persistance de Polaris dans Postgres. Validé par un namespace de test
   conservé après un redémarrage complet (`docker compose down` /
   `up -d`).

3. **Premier script d'ingestion** : Open-Meteo (gratuite, sans clé API).
   Un script Python appelle l'API et écrit une table Iceberg avec PyIceberg
   dans RustFS, via le catalogue Polaris. Il est lancé à la main, sans
   orchestration.

4. **ClickHouse** : ajout au compose, et lecture de la table Iceberg de
   l'étape 3.

5. **Squelette dbt** : projet minimal avec un premier modèle Silver sur la
   table de l'étape 3, pour valider la connexion `dbt-clickhouse`.

6. **Orchestration Prefect** : flow d'ingestion, puis flow qui déclenche
   `dbt run`.

7. **Autres sources** : Enedis et ODRE, sur le même modèle que le flux
   Open-Meteo (écriture Iceberg, lecture ClickHouse, modèles dbt).

8. **Metabase** : premier tableau de bord sur les tables Gold.

9. **Tests et CI**, en continu à chaque étape : tests unitaires puis
   d'intégration, enrichissement du workflow GitHub Actions.
