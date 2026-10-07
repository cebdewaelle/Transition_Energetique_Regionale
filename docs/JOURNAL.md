# Journal de bord

Suivi d'avancement du projet, tenu au fil de l'eau. Sert à reprendre le
fil d'une session à l'autre et de matière brute pour préparer la
soutenance (difficultés rencontrées, décisions prises et pourquoi).

## Format d'une entrée

```
## AAAA-MM-JJ

**Objectif du jour** :
**Fait** :
**Bloqué sur / décisions prises** :
**Prochaine étape** :
```

---

## 2026-09-26

**Objectif du jour** : démarrer concrètement la mise en place du projet.

**Fait** :
- Liste des outils à installer et ordre de construction du projet
  (feuille de route) définis.
- Création de ce journal.
- Identifié un point à garder en tête : travail sur deux machines
  (portable Linux natif en formation, PC fixe Windows + WSL2 en perso) —
  le repo Git est le seul lien entre les deux, les volumes Docker
  (RustFS, ClickHouse) restent locaux à chaque machine et sont
  reconstruits via le pipeline (d'où l'importance d'un chargement
  idempotent).
- Outils système vérifiés/mis à jour sur le PC fixe (WSL2) :
  - Docker mis à jour 29.0.2 → 29.8.1, Docker Compose en v2.39.1
    (intégration Docker Desktop/WSL2).
  - Python 3.12.3 déjà présent, suffisant (minimum requis : 3.11+).
  - `uv` 0.12.19 installé (absent auparavant).

**Bloqué sur / décisions prises** : aucune décision d'architecture
nouvelle — celles-ci (RustFS, Apache Polaris) avaient déjà été actées lors
des sessions précédentes.

**Prochaine étape** : vérifier/installer les mêmes outils sur le portable
Linux (formation) pour garder les deux machines alignées, puis initialiser
la structure du repo (étape 1 de la feuille de route).

## 2026-09-27

**Objectif du jour** : faire le ménage dans Docker et initialiser le projet
Python.

**Fait** :
- Suppression des restes d'un ancien projet : 4 volumes et 7 images 
  qui vont entrer en conflit avec ceux nécéssaires au projet. 
- Découverte de **deux moteurs Docker en parallèle** sur le PC fixe : le
  Docker Engine natif installé via apt dans WSL2 (contexte `default`) et
  celui de Docker Desktop (contexte `desktop-linux`). Le nettoyage a dû être
  refait dans l'interface de Docker Desktop (après redémarrage de l'app),
  car ce moteur n'est pas joignable depuis WSL2.
- Initialisation du projet avec `uv` (src layout :
  `src/transition_energetique_regionale/`, tests dans `tests/` à la
  racine), premier smoke test pytest qui vérifie que le paquet s'importe.
- Installation de l'extension VS Code Conventional Commits (vivaxy).

**Bloqué sur / décisions prises** :
- Choisir un seul moteur Docker pour le projet — **toujours ouvert**.
  Recommandation : garder Docker Desktop avec intégration WSL2 et
  désinstaller le `docker-ce` natif.

**Prochaine étape** : mettre en place la validation des messages de commit
et la CI.

## 2026-09-28

**Objectif du jour** : outillage Git (commits conventionnels, branches) et
première CI GitHub Actions.

**Fait** :
- **commitizen** configuré dans `pyproject.toml` (`version_provider = "uv"`,
  `pep440`, tags `v$version`, changelog automatique au bump, version
  majeure bloquée à 0) et branché en hook `commit-msg` via **pre-commit**
  (`.pre-commit-config.yaml`, commitizen v4.19.0). Les messages non
  conformes sont refusés au moment du commit.
- Gitmoji adopté, placé après le type (`build: :tada: …`) pour rester
  compatible avec la règle de commitizen.
- Locale `en_US.UTF-8` générée dans WSL2 : VS Code l'impose pour lancer
  Git, son absence provoquait un avertissement.
- Authentification GitHub corrigée : le fine-grained token de `gh` n'avait
  pas accès en écriture au dépôt (erreur 403 au push). Reconnexion via
  `gh auth login` avec le scope `workflow`.
- Modèle de branches : `main` (stable) / `develop` (intégration) /
  `feature/*`.
- CI GitHub Actions (`.github/workflows/ci.yml`) : checkout, `setup-uv`,
  `uv sync --locked`, `uv run pytest`. **Verte**, PR #1 fusionnée dans
  `develop`.
- Portable Linux aligné : clone du dépôt, `uv`, `uv sync`, smoke test OK,
  hook commitizen actif, fine-grained token dédié au portable.
- Fine-grained token du PC complété (permissions Pull requests et Actions) :
  un jeton par machine, limité à ce dépôt.
- **Décision : moteur Docker natif uniquement, Docker Desktop désinstallé.**
  Raisons : même configuration que le portable (moteur natif), plus léger,
  et fin des conflits. L'intégration WSL2 de Docker Desktop masquait le
  plugin `compose` installé par apt et prenait la place du socket
  `/var/run/docker.sock`. Après désinstallation : ligne `credsStore`
  retirée de `~/.docker/config.json`, contexte `desktop-linux` supprimé,
  liens de plugins morts supprimés, socket recréé.
- Pour remplacer l'interface de Docker Desktop : extension Container Tools
  de VS Code.

**Difficultés rencontrées** :
- Extension Conventional Commits : le réglage `lineBreak` est transformé en
  expression régulière sans échappement. Avec `|`, un retour à la ligne
  était inséré entre chaque caractère du message. Solution : `\n`.
- Premier run CI en échec : `astral-sh/setup-uv` ne publie pas de tag de
  version majeure flottant (`@v10` introuvable), contrairement à
  `actions/checkout@v7`. Épinglé en version complète `@v10.2.0`.

**Prochaine étape** : étape 2 de la feuille de route, RustFS + Polaris dans
un premier `docker-compose.yml`, sur une branche `feature/…` créée depuis
`develop`.

## 2026-09-28 (suite)

**Objectif du jour** : étape 2 de la feuille de route, stockage RustFS et
catalogue Polaris dans un premier `docker-compose.yml`.

**Fait** :
- Branche `feature/rustfs-polaris` créée depuis `develop`.
- `docker-compose.yml` construit à partir des exemples officiels de Polaris
  (sources et licence Apache 2.0 citées en en-tête), puis adapté :
  - versions figées : RustFS 1.0.0, Polaris 1.8.0, outil d'administration
    Polaris 1.8.0, Postgres 18.6 ;
  - volumes persistants pour RustFS et Postgres ;
  - identifiants dans un `.env` non versionné, `.env.example` versionné ;
  - port de débogage Java retiré, pas de port Postgres publié ;
  - noms propres au projet : bucket `transition-energetique-regionale`,
    catalogue `ter_catalog`.
- Scripts d'initialisation du catalogue dans `docker/polaris/` : obtention
  du jeton OAuth, création du catalogue, ajout des droits.
- **Persistance de Polaris dans Postgres** (mode `relational-jdbc`) : service
  `postgres`, service ponctuel `polaris-bootstrap` qui initialise le royaume
  `POLARIS`, schéma `polaris_schema` créé au premier démarrage
  (`docker/postgres/create-polaris-schema.sql`).
- `create-catalog.sh` rendu idempotent : il vérifie si le catalogue existe
  (`GET`) avant de le créer. 200 → création sautée, 404 → création, autre
  code → erreur.
- Validation : bucket visible dans la console RustFS, jeton obtenu depuis
  l'hôte, catalogue listé, namespace `test` créé puis retrouvé après un
  `docker compose down` / `up -d`.
- `jq` installé pour lire les réponses de l'API.

**Difficultés rencontrées** :
- **Chemins de montage** : l'exemple officiel monte `../assets/polaris`, un
  chemin relatif à l'arborescence du dépôt Polaris. Chez moi, Docker a créé
  un dossier vide (appartenant à root) en dehors du projet, et le script
  était introuvable dans le conteneur. Solution : scripts copiés dans
  `docker/polaris/`. Retenu : `hôte:conteneur`, et une commande exécutée
  dans le conteneur ne voit que les chemins du conteneur.
- **Volumes mal placés** : le volume RustFS était monté sur un autre
  dossier que celui où RustFS écrit (`RUSTFS_VOLUMES=/data`), donc rien
  n'était conservé. Même piège évité pour Postgres 18, dont les données
  sont sous `/var/lib/postgresql/18/docker` : volume monté sur
  `/var/lib/postgresql` (vérifié avec `docker image inspect`).
- **Console RustFS** : elle est sous `/rustfs/console/`, la racine du port
  9001 renvoie une erreur 403.
- **Polaris en mémoire** : un redémarrage effaçait le catalogue et
  régénérait la clé de signature des jetons (erreur 401 « Failed to verify
  the token »). D'où la persistance Postgres.
- **Secret visible dans les logs** : l'outil d'administration affiche sa
  ligne de commande complète, donc le secret admin passé via
  `--credential`. Solution : option `--credentials-file`, avec un fichier
  généré par Compose (`configs`) à partir du `.env`, qui n'existe jamais
  sur le disque du projet. Secret admin changé ensuite.
- **Priorité des variables** : des variables exportées dans le shell
  (`set -a; source .env`) l'emportent sur le `.env` pour Compose. Le
  bootstrap avait utilisé l'ancien secret resté dans le terminal. Retenu :
  charger le `.env` dans un sous-shell, `( set -a; source .env; set +a; … )`.
- **Redémarrage avec Postgres** : `polaris-setup` échouait (code 22 de
  `curl`) car le catalogue existait déjà. Le bootstrap, lui, était déjà
  idempotent (« already bootstrapped; skipping »).

**Décisions prises** :
- Persistance de Polaris dans Postgres dès maintenant, avant toute
  ingestion de vraies données.
- Identifiants passés par fichier plutôt qu'en argument de commande quand
  un outil affiche ses arguments dans les logs.

**Points en suspens** :
- Clé de signature des jetons Polaris régénérée à chaque redémarrage : les
  jetons en cours deviennent invalides (sans impact pour les clients qui
  redemandent un jeton automatiquement, comme PyIceberg).
- Barre de progression du `curl` des droits dans les logs de
  `polaris-setup` (ajouter `-s`).

**Prochaine étape** : commit et PR de `feature/rustfs-polaris` vers
`develop`, puis étape 3 : premier script d'ingestion Open-Meteo avec
PyIceberg.

## 2026-10-06

**Objectif du jour** : finir d'installer les outils en ligne de commande
avant de passer à l'ingestion.

**Fait** :
- PR #2 (stockage et catalogue) fusionnée dans `develop`.
- **AWS CLI v2** installée avec l'installateur officiel (le paquet apt
  `awscli` est l'ancienne version 1), et un profil `rustfs` :
  identifiants RustFS, `endpoint_url` sur `http://localhost:9000`,
  `s3.addressing_style` en `path`. Vérifié avec
  `aws --profile rustfs s3 ls` : le bucket est bien retrouvé dans le
  volume.
- **DuckDB 1.5.6** installé.
- Client `rc` de RustFS écarté (redondant avec AWS CLI, version 0.1.x).
- `clickhouse-client` non installé en local : j'utiliserai celui de
  l'image du serveur, toujours à la même version.

**Difficultés rencontrées** :
- **Configuration AWS sur le disque Windows** : `~/.aws` était un lien
  vers le dossier Windows de mon profil, créé par un outil installé
  auparavant. La configuration, clé secrète comprise, s'est donc
  retrouvée côté Windows, où les droits Linux ne s'appliquent pas (tous
  les fichiers y apparaissent en `777`). Remplacé par un vrai dossier
  Linux (droits `700` pour le dossier, `600` pour les fichiers), et
  copie Windows supprimée.

**Prochaine étape** : clarifier les sources de données avant d'écrire le
premier script d'ingestion.

## 2026-10-07

**Objectif du jour** : choisir précisément les données à utiliser et
remettre à plat la documentation.

**Fait** :
- Documentation réorganisée : `docs/` contient le journal et la feuille
  de route (PR #3 fusionnée dans `develop`).
- README revu : moins détaillé, sans les éléments qui n'existent pas
  encore (nombre de tests, tables, résultats chiffrés), avec Polaris et
  PostgreSQL dans la stack, les tests et la CI formulés comme une cible,
  et des sources citées pour chaque explication. Schéma d'architecture
  retiré pour l'instant : je préfère une image à un schéma en texte.
- Sources de données choisies et vérifiées directement sur les API des
  portails.

**Décisions prises** :
- **Granularité régionale, sans codes IRIS** : les 12 régions
  métropolitaines couvertes par éCO2mix (la Corse n'y figure pas).
  Partir de données déjà publiées par région évite la correspondance
  IRIS → région, les changements de codes géographiques dans le temps et
  le masquage des petites zones pour secret statistique.
- **Sources** :
  - éCO2mix régional consolidé et définitif (ODRE) : consommation et
    production par filière, au pas de 30 minutes, depuis 2013. Il fournit
    aussi les taux de couverture et de charge calculés par RTE, qui
    serviront de référence pour tester mes propres calculs ;
  - registre national des installations de production (ODRE) :
    puissance installée par filière et par commune.
- **Météo par région** : Open-Meteo raisonne par points, pas par zones.
  Un point par département, puis une moyenne régionale pondérée selon ce
  que chaque variable explique : température → population, vent à
  100 m → puissance éolienne installée, rayonnement → puissance solaire
  installée, précipitations et neige (en cumuls) → puissance hydraulique
  installée.
- **DJU** : méthode « météo », base 18 °C, calculés par département puis
  agrégés par région. La méthode COSTIC est gardée pour une version
  ultérieure.
- **Hydraulique** : analysée au mois ou à la saison, car les barrages
  sont pilotés selon la demande et la pluie agit avec un décalage.
  **Bioénergies** : filières pilotables, sans indicateur météo. Hypothèse
  à tester : la cogénération suivrait les DJU.
- Terme retenu : « hydraulique », comme dans les données (éCO2mix et
  registre).

**Difficultés rencontrées** :
- Le portail Enedis propose des centaines de jeux de données : il a été
  plus efficace de partir de la question (comparer des régions) que des
  données disponibles.
- Faire correspondre les codes IRIS et les points météo n'était pas
  possible simplement : la granularité régionale et la pondération par
  département règlent les deux problèmes.

**Prochaine étape** : étape 3, table de référence des départements et
premier script d'ingestion Open-Meteo.
