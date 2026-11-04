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

------------------------------------------------------------------------------
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

------------------------------------------------------------------------------
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

------------------------------------------------------------------------------
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

------------------------------------------------------------------------------
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

------------------------------------------------------------------------------
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

------------------------------------------------------------------------------
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

------------------------------------------------------------------------------
## 2026-11-02

**Objectif du jour** : organiser l'étape 3 et valider l'écriture d'une table
Iceberg depuis Python.

**Fait** :
- Étape 3 découpée : test d'écriture, table de référence des départements,
  puis ingestion Open-Meteo, d'abord sur un petit périmètre.
- `pyiceberg` et `python-dotenv` ajoutés au projet.
- **Test d'écriture de bout en bout réussi**, avec un script jetable :
  connexion à Polaris, création du namespace `bronze`, écriture de 3 lignes
  dans une table de test, relecture, puis purge de la table. Les fichiers de
  données et de métadonnées sont apparus dans le bucket, puis ont disparu
  après la purge.
- Lecture de la structure d'une table Iceberg dans le bucket : fichiers
  Parquet (`data/`), versions de la table (`metadata.json`), snapshots et
  manifests (`.avro`).

**Décisions prises** :
- **Connexion à Polaris en tant que catalogue REST** : PyIceberg ne connaît
  pas Polaris en tant que tel, seulement le protocole REST d'Iceberg.
- **Pas de clés RustFS côté client** : les identifiants Polaris suffisent,
  Polaris fournit l'accès au stockage (`vended-credentials`, comportement par
  défaut de PyIceberg).
- **Point météo de chaque département** : centre géographique, approché par
  la moyenne des centres des communes. L'API Géo ne donne ni centre ni
  population au niveau du département, ces deux valeurs sont donc agrégées à
  partir des communes.
- La chaîne sera d'abord validée sur **2 ans de données, 2024 et 2025**, avant
  de lancer l'historique complet : ce sont les deux dernières années complètes
  et en « données définitives » d'éCO2mix. Côté Open-Meteo, cela représente
  environ 4 900 appels, à étaler sur plus d'une heure.

**Difficultés rencontrées** :
- **Limites de l'offre gratuite d'Open-Meteo** : 600 appels par minute, 5 000
  par heure, 10 000 par jour et 300 000 par mois. Une requête de plus de
  2 semaines compte pour plusieurs appels : l'historique complet représente
  environ 33 500 appels pour 94 départements, soit au moins 4 jours de
  téléchargement. Il faudra découper par année, gérer les réessais (l'API
  renvoie parfois une erreur 503) et permettre la reprise.
- **Documentation** : rien sur « Polaris » dans la documentation de
  PyIceberg, il faut chercher « REST Catalog ».
- **Trou dans des données « définitives »** : dans l'export éCO2mix téléchargé
  en octobre, Auvergne-Rhône-Alpes s'arrête le 16 février 2025, soit 15 270
  lignes manquantes. Le 7 octobre, la source annonçait le même nombre de lignes
  que ce fichier (2 859 546). Elle en compte aujourd'hui 2 874 816, avec une
  année 2025 complète pour cette région : le trou était donc très probablement
  dans la source, corrigé depuis. Seuls les nombres de lignes ont été comparés.
  Conséquences :
  - export à retélécharger avant l'étape 7 ;
  - test de complétude à prévoir dans dbt : 17 520 lignes par région et par an,
    17 568 pour une année bissextile ;
  - chargement incrémental à concevoir pour pouvoir recharger des périodes
    passées, et pas seulement les nouvelles dates.

**Références** :
- [PyIceberg, configuration du catalogue REST](https://py.iceberg.apache.org/configuration/#rest-catalog)
- [PyIceberg, API Python (namespaces, tables, écriture, lecture)](https://py.iceberg.apache.org/api/)
- [Open-Meteo, limites et décompte des appels](https://open-meteo.com/en/pricing)
- [API Géo](https://geo.api.gouv.fr/)

**Prochaine étape** : table de référence `bronze.ref_departements`, puis
ingestion Open-Meteo sur un département et un mois.

------------------------------------------------------------------------------
## 2026-11-03

**Objectif du jour** : table de référence des départements et première
ingestion Open-Meteo.

**Fait** :
- **Table `bronze.ref_departements`** : 94 départements, avec leur région,
  leur centre (moyenne des centres des communes) et leur population, à partir
  de l'API Géo. Contrôlée sur le nombre de lignes et les valeurs du Nord, de
  Paris et de l'Isère. Colonne `date_extraction` ajoutée par évolution de
  schéma Iceberg, sans recréer la table.
- **Table `bronze.meteo_horaire`** : ingestion d'Open-Meteo sur un département
  et un mois (Nord, janvier 2024), soit 744 lignes, sans valeur vide,
  partitionnées par mois. Horodatages en UTC. Six variables : température à
  2 m, vent à 100 m (en m/s), rayonnement, précipitations, chutes de neige et
  épaisseur de neige.
- Contrôle du nombre de lignes avant écriture : départements × jours × 24.
- Tests unitaires (42) sans réseau ni Docker, exécutés aussi en CI : calculs,
  appels API simulés, schémas, contrôles avant écriture, partitionnement.

**Décisions prises** :
- **`requests` et JSON** plutôt que le client `openmeteo-requests` : lecture
  des variables par leur nom et non par leur position, tests plus simples, gain
  de performance négligeable ici. Pas d'asynchrone : la contrainte est la
  limite d'appels de l'API, pas la vitesse.
- **Pas de cache de requêtes** : la table Iceberg joue ce rôle, et un cache
  pourrait masquer des données corrigées à la source.
- **Fuseau `GMT`** pour Open-Meteo. Avec un fuseau local, l'API applique un
  décalage fixe calculé au moment de la requête, sans tenir compte des
  changements d'heure de la période demandée. Le résultat serait décalé d'une
  heure sur une partie de l'année.

**Difficultés rencontrées** :
- **Changements d'heure dans éCO2mix** : la source compte toujours 48 lignes
  par jour local, alors que ces journées durent 23 ou 25 heures. Observé sur
  les Hauts-de-France en 2024 :
  - le 31 mars, l'heure locale 02:00-02:30, qui n'existe pas, est présente et
    reprend les instants et les valeurs de 03:00-03:30 : 2 doublons ;
  - le 27 octobre, les relevés de 00:00 et 00:30 UTC sont absents : 2 demi-heures
    manquantes.

  Sur une année complète, doublons et trou se compensent : le nombre de lignes
  est juste alors que les données ne le sont pas. Sur la colonne `date`, le
  comptage ne détecte jamais rien. À confirmer sur toutes les régions et années.
  Conséquences pour Silver : filtrer et joindre uniquement sur `date_heure`,
  dédoublonner, et tester l'unicité et la continuité, en plus du comptage.
- **Écriture partitionnée** : le calcul des partitions demande le composant
  `pyiceberg-core`, à installer en plus.
- **Purge refusée par Polaris** : `purge_table` est désactivée par défaut
  (`DROP_WITH_PURGE_ENABLED`), et `drop_table` ne supprime pas les fichiers.
- **Anciens fichiers Parquet** : un `overwrite` ne supprime rien physiquement.
  Les fichiers restent accessibles par les anciens snapshots, c'est le principe
  du time travel. Ils ne doivent pas être supprimés à la main.
- **Données modélisées** : Open-Meteo peut indiquer de la neige par 7 °C au sol
  (0,14 cm le 1er janvier 2024 dans le Nord). Valeur conservée en Bronze, à
  contrôler en Silver.

**Références** :
- [Open-Meteo, API météo historique](https://open-meteo.com/en/docs/historical-weather-api)
- [PyIceberg, évolution du partitionnement](https://py.iceberg.apache.org/api/#partition-evolution)

**Suite de la journée** : passage aux 94 départements et aux 2 années.

**Fait** :
- **`bronze.meteo_horaire` chargée sur 2024 et 2025** : 1 649 136 lignes,
  24 partitions, 94 départements avec 17 544 heures chacun, sans doublon ni
  valeur vide.
- Écriture par mois, tous départements confondus : chaque lot remplace
  uniquement son mois, et n'est écrit que lorsque les 94 départements sont
  récupérés.
- Réessais automatiques en cas de limite d'appels ou d'erreur serveur, pause
  d'une seconde entre les appels, et reprise qui saute les mois déjà complets.
- Comportement vérifié sur une table Iceberg jetable (écriture, relance sans
  appel à l'API, panne, reprise), puis en conditions réelles.

**Décisions prises** :
- **Un lot = un mois** : le lot correspond à une partition, une panne coûte au
  plus un mois, et l'écriture par département aurait créé 2 256 commits et
  autant de petits fichiers.

**Difficultés rencontrées** :
- **Expiration des identifiants après une heure** : le téléchargement s'est
  arrêté en septembre 2025 sur une erreur `ACCESS_DENIED`. Les identifiants S3
  temporaires fournis par Polaris sont valables 60 minutes, et la table n'était
  ouverte qu'une fois au démarrage. Les 20 premiers mois étaient intacts, et la
  reprise a terminé les 4 derniers. Correction : rouvrir la table avant chaque
  écriture. Un test simulé ne pouvait pas le montrer : le bug n'apparaît
  qu'après une heure d'exécution réelle.
- **Durée sous-estimée** : un mois prend près de 3 minutes, soit environ
  70 minutes pour 2 ans.
- **Table neuve** : `inspect.partitions()` lève une erreur tant que la table
  n'a jamais été écrite. Découvert en testant sur une vraie table.
- **Filtre d'écriture** : un filtre couvrant toute la période aurait effacé les
  mois précédents à chaque écriture. Détecté avant le lancement.

**Limites à garder en tête** :
- **Montagne mal représentée** : un point par département reste bas, 827 m pour
  les Hautes-Alpes, et 1 303 m au plus haut (Cantal).
- **532 lignes de neige avec plus de 5 °C** (0,03 %), à contrôler en Silver.
- **DuckDB affiche les horodatages dans le fuseau local** : les données sont bien
  en UTC, mais les calculs d'heure doivent préciser le fuseau.

**Prochaine étape** : étape 4, ajouter ClickHouse et lire les tables Iceberg.

------------------------------------------------------------------------------
## 2026-11-04

**Objectif du jour** : étape 4, ajouter ClickHouse et lui faire lire les tables
Iceberg.

**Fait** :
- **Service `clickhouse`** dans le compose (version 26.8.36.3, LTS) : volume
  persistant, identifiants dans le `.env`, healthcheck sur `/ping`.
- **Base `polaris`** créée au premier démarrage par un script d'initialisation,
  avec le moteur `DataLakeCatalog`. ClickHouse voit les tables du catalogue sans
  import : 94 départements et 1 649 136 lignes de météo.
- Jointure validée entre la météo et les départements : température de janvier
  2024 pondérée par la population, 3,89 °C pour l'Île-de-France.
- **Time travel validé dans ClickHouse** (`iceberg_snapshot_id` et
  `iceberg_timestamp_ms`), en lecture d'un ancien snapshot.
- Connexion conservée après un `docker compose down` puis `up -d`.

**Décisions prises** :
- **Clés RustFS configurées dans ClickHouse** (`vended_credentials = 0`) : avec
  les identifiants fournis par Polaris, la lecture échoue en 404. Cause probable,
  non prouvée : l'endpoint `localhost:9000` transmis aux clients, qui ne désigne
  pas RustFS depuis un conteneur.
- **Seul le port HTTP 8123 est publié** : le port natif 9000 de ClickHouse reste
  interne, RustFS occupe déjà ce port sur la machine.

**Difficultés rencontrées** :
- **Script d'initialisation** : SQL placé directement dans un fichier `.sh`, donc
  exécuté par bash (`SET: command not found`). Le SQL doit être transmis à
  `clickhouse-client`. Le script ne s'exécute que si le volume est vide : après
  un échec, il faut supprimer le volume pour le relancer.
- **Clés stockées dans la base** : si une clé change, il faudra supprimer et
  recréer la base `polaris`.
- **Syntaxe des tables** : le nom complet s'écrit entre backticks,
  `` polaris.`bronze.meteo_horaire` ``.

**Références** :
- [ClickHouse, guide du catalogue Polaris](https://github.com/ClickHouse/ClickHouse/blob/fb4661a3478a/docs/guides/use-cases/data-warehousing/polaris-catalog.mdx)
- [ClickHouse, moteur de base DataLakeCatalog](https://github.com/ClickHouse/ClickHouse/blob/master/docs/reference/engines/database-engines/datalake.mdx)

**Prochaine étape** : étape 5, squelette dbt avec un premier modèle Silver.

------------------------------------------------------------------------------
## 2026-11-04 (suite)

**Objectif du jour** : étape 5, squelette dbt avec un premier modèle Silver.

**Fait** :
- **Projet dbt** dans `dbt/`, avec `dbt-core` 1.12.6 et `dbt-clickhouse` 1.10.3.
  Les identifiants du profil viennent des variables d'environnement.
- **Sources** déclarées sur les tables Iceberg vues par ClickHouse.
- **Modèle `silver.silver_meteo_horaire`** : 1 649 136 lignes dans une table
  MergeTree, triée par département et heure, partitionnée par mois.
- **21 tests dbt** : valeurs vides sur toutes les colonnes et sur la source,
  unicité du référentiel et du couple département/heure, relation avec le
  référentiel, complétude de chaque mois, plages de valeurs plausibles.

**Décisions prises** :
- **Base `silver` plutôt que `default_silver`** : surcharge de la macro
  `generate_schema_name`. Le préfixe de dbt sert à séparer les développeurs d'une
  équipe, inutile ici, et les noms suivent l'architecture médaillon.
- **`date_extraction` conservée en Silver** : peu coûteuse, utile pour la
  traçabilité et le contrôle de fraîcheur.

**Difficultés rencontrées** :
- **Nom de table avec un point** : `bronze.meteo_horaire` est un seul nom côté
  ClickHouse. La source doit l'indiquer dans `identifier`, avec `quoting`, pour
  qu'il soit mis entre backticks.
- **Colonnes nullable** : les colonnes Iceberg sont nullable, et ClickHouse les
  refuse dans une clé de tri ou de partition. `assumeNotNull` règle le problème,
  mais remplace une valeur vide sans le signaler : d'où les tests `not_null` sur
  la source elle-même.
- **Modèle vide** : un fichier non enregistré donne `Nothing to do`, sans erreur.
- **`.env`** : dbt le charge seul, en remontant depuis le dossier courant. Une
  variable déjà présente dans le terminal reste prioritaire.
- **Extension VS Code** : elle utilise son propre moteur et ne voit pas ces
  variables, d'où une erreur dans l'éditeur alors que la ligne de commande
  fonctionne.

**Limite** : les tests dbt ne tournent pas encore en CI, car ils ont besoin du
stack complet.

**Prochaine étape** : étape 6, orchestration avec Prefect.

------------------------------------------------------------------------------
