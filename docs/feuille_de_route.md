# Feuille de route

Ordre de construction du projet et outils utilisés. Le détail de
l'avancement (difficultés rencontrées, décisions prises) est consigné dans
`JOURNAL.md`.

## Principe

Je construis d'abord un flux complet de bout en bout sur une seule source
de données simple (Open-Meteo), avant d'étendre aux autres sources (données
éCO2mix et registre des installations, publiés sur l'ODRE) et aux
indicateurs. Chaque brique est validée manuellement avant d'être
orchestrée.

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
      `s3.addressing_style` en `path`), configuré dans un dossier `~/.aws`
      Linux. J'ai écarté le client `rc` de RustFS : redondant avec AWS
      CLI, et encore en version 0.1.x.
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

3. ✅ **Premier script d'ingestion** (2026-11-03) : Open-Meteo (gratuite, sans
   clé API). Un script Python récupère la météo historique en un point par
   département métropolitain (centre du département) : température, vent à
   100 m, rayonnement solaire, précipitations et neige. Il écrit par mois dans
   une table Iceberg, avec PyIceberg, via le catalogue Polaris, à partir d'une
   table de référence des 94 départements. Il peut être relancé après une
   interruption, sans doublon. Il est lancé à la main, sans orchestration.
   Chargé sur 2024 et 2025 : 1 649 136 lignes, sans doublon ni valeur vide.

4. ✅ **ClickHouse** (2026-11-04) : ajout au compose, et lecture des tables
   Iceberg de l'étape 3 via le catalogue Polaris, sans import. Jointures et time
   travel validés, connexion conservée après un redémarrage complet.

5. ✅ **Squelette dbt** (2026-11-04) : projet minimal avec un premier modèle
   Silver sur la table de l'étape 3, `silver.silver_meteo_horaire`, et tests de
   qualité sur la source et le modèle (valeurs vides, unicité, complétude,
   plages de valeurs).

6. **Orchestration Prefect** : flow d'ingestion, puis flow qui déclenche
   `dbt run`.

7. **Autres sources** : éCO2mix régional et registre national des
   installations (ODRE), sur le même modèle que le flux Open-Meteo
   (écriture Iceberg, lecture ClickHouse, modèles dbt). C'est à cette
   étape que la météo est agrégée par région, avec les pondérations
   décrites dans le README.

8. **Metabase** : premier tableau de bord sur les tables Gold.

9. **Tests et CI**, en continu à chaque étape : tests unitaires puis
   d'intégration, enrichissement du workflow GitHub Actions.

## Pistes pour une version ultérieure

- DJU calculés aussi avec la méthode COSTIC, pour comparer laquelle suit
  le mieux la consommation.
- Débits des rivières (Hub'Eau) pour mieux expliquer la production
  hydraulique.
- Consommation par secteur (résidentiel, tertiaire, industrie), via
  l'Agence ORE.
- Filières non renouvelables (nucléaire, thermique fossile), déjà présentes dans
  éCO2mix.
- Zoom infrarégional (départements, voire IRIS).
