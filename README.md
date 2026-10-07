# Transition_Energetique_Regionale

L'idée est de créer une plateforme qui compare la consommation réelle à la production d'énergies renouvelables (éolien, solaire, hydraulique, bioénergies) par région avec prise en compte de la météo (température, ensoleillement, vent, précipitations, neige).

**Le défi** : croiser des séries de consommation et de production électriques sur plus de dix ans, au pas de 30 minutes, avec des données météo historiques, à l'échelle des régions métropolitaines françaises.

**Pipeline prévu** :

- **Ingestion (Python)** : récupération des données ODRE et Open-Meteo, écrites sous forme de tables Apache Iceberg (via PyIceberg) dans RustFS et référencées dans le catalogue Apache Polaris.
- **Stockage brut (Bronze)** : tables Iceberg au format Parquet sur RustFS (schema evolution, time travel, chargement incrémental).
- **Transformation (Silver/Gold)** : dbt s'exécute sur ClickHouse (via dbt-clickhouse). ClickHouse lit les tables Iceberg via le catalogue Polaris, sans import préalable.
- **Tables finales (Gold)** : tables ClickHouse MergeTree optimisées pour les agrégations analytiques.
- **Qualité des données** : tests dbt pour détecter les valeurs aberrantes, vérifier la cohérence des unités et la fraîcheur des données.

La météo apporte quatre dimensions :

- la **température** → la consommation : corrélation entre le froid et les pics de consommation, et normalisation via les DJU (Degrés Jour Unifiés). Les DJU de chauffage mesurent, pour chaque jour, l'écart entre une température de référence, habituellement 18 °C, et la température moyenne du jour : plus l'hiver est rigoureux, plus ils sont élevés, ce qui permet de comparer des hivers entre eux. Le projet utilise la méthode dite « météo » : DJU = 18 − (Tmin + Tmax) / 2, ramené à 0 lorsque le résultat est négatif. Les DJU sont calculés pour chaque département, puis agrégés par région en pondérant par la population.
  *Source : [Wikipédia, Degré jour unifié](https://fr.wikipedia.org/wiki/Degr%C3%A9_jour_unifi%C3%A9).*

- la **vitesse du vent** → la production éolienne : la plupart des éoliennes démarrent à partir d'un vent d'environ 3 m/s et s'arrêtent par sécurité vers 25 m/s. Entre ces deux seuils, la puissance produite augmente environ comme le cube de la vitesse du vent (de 3 à 10 m/s), puis plafonne à la puissance maximale de l'éolienne. Le vent permet donc d'expliquer pourquoi la production éolienne varie autant d'un jour à l'autre, d'une saison à l'autre et d'une région à l'autre, et de distinguer une année peu venteuse d'un parc éolien qui progresse peu.
  *Sources : [Connaissance des énergies, Énergie éolienne](https://www.connaissancedesenergies.org/fiche-pedagogique/energie-eolienne) ; [Wikipédia, Éolienne](https://fr.wikipedia.org/wiki/%C3%89olienne).*

- l'**ensoleillement** (rayonnement solaire reçu au sol) → la production solaire : l'électricité photovoltaïque est produite en convertissant une partie du rayonnement solaire, et son rendement dépend de l'ensoleillement, d'où de fortes variations selon le lieu et les conditions météorologiques. Le rayonnement est plus pertinent que la durée d'ensoleillement : à Rouen, par exemple, environ 1 750 heures d'ensoleillement par an ne correspondent qu'à près de 1 100 heures de production à pleine puissance. Il permet d'expliquer les écarts entre le nord et le sud, entre l'été et l'hiver, et de séparer l'effet de la météo de celui de l'augmentation du nombre de panneaux installés.
  *Sources : [Connaissance des énergies, Solaire photovoltaïque](https://www.connaissancedesenergies.org/fiche-pedagogique/solaire-photovoltaique) ; [Wikipédia, Énergie solaire photovoltaïque](https://fr.wikipedia.org/wiki/%C3%89nergie_solaire_photovolta%C3%AFque).*

- les **précipitations et la neige** → la production hydraulique : les centrales au fil de l'eau turbinent le débit de la rivière au moment où il arrive, alors que les centrales de lac stockent l'eau derrière un barrage et la turbinent aux heures où l'électricité est la plus nécessaire, notamment pendant les pointes de consommation. Les stations de transfert d'énergie par pompage (STEP) servent, elles, au stockage. La pluie ne se retrouve donc pas dans la production du jour même : elle agit avec un décalage, à travers les débits des rivières. La neige est une réserve d'eau, dont la fonte au printemps et au début de l'été alimente les rivières de montagne. L'hydraulique s'analyse donc plutôt au mois ou à la saison (année sèche ou humide, effet de la fonte des neiges), avec des cumuls de précipitations sur plusieurs semaines, et surtout dans les régions de montagne et de grands fleuves.
  *Source : [Connaissance des énergies, Hydroélectricité](https://www.connaissancedesenergies.org/fiche-pedagogique/hydroelectricite).*

Les **bioénergies** (biomasse, biogaz, incinération des déchets), elles, brûlent un combustible stockable : comme le nucléaire ou le thermique fossile, ce sont des filières pilotables, dont la production dépend du parc installé et de son exploitation, pas de la météo. Elles sont suivies par leur taux de charge et par l'évolution du parc. Une hypothèse sera testée : les installations en cogénération, qui produisent à la fois de l'électricité et de la chaleur pour des réseaux de chauffage, devraient produire davantage en hiver, et donc suivre les DJU.
*Sources : [Wikipédia, Énergie renouvelable](https://fr.wikipedia.org/wiki/%C3%89nergie_renouvelable) ; [Connaissance des énergies, Biomasse](https://www.connaissancedesenergies.org/fiche-pedagogique/biomasse).*


# L'architecture technique

## Stack (100 % gratuite, 100 % open-source)

- **Orchestration** : Prefect 3 (planification de l'ingestion quotidienne/mensuelle — plus léger et moderne qu'Airflow, interface web intégrée).
- **Ingestion** : Python (API Open Data Réseaux Énergies - ODRE, et Open-Meteo pour la météo).
- **Stockage (Data Lake)** : RustFS (stockage objet compatible S3) + Apache Iceberg, format de table ouvert pour les données brutes (Bronze).
- **Catalogue Iceberg** : Apache Polaris, avec ses métadonnées persistées dans PostgreSQL.
- **Transformation (Data Warehouse)** : ClickHouse comme moteur OLAP + dbt (via dbt-clickhouse) pour les transformations SQL.
- **Qualité des données** : tests dbt (schéma et contenu) + pytest (tests unitaires et d'intégration).
- **Visualisation** : Metabase (connecteur ClickHouse natif, gratuit).
- **Conteneurisation** : Docker / Docker Compose pour faire tourner tous les services localement.

**Tests & CI/CD (cible)** : pytest avec des tests unitaires et d'intégration, et un workflow GitHub Actions qui exécute pytest, `dbt run` et `dbt test`. En place aujourd'hui : workflow GitHub Actions lançant pytest, commits conventionnels vérifiés par commitizen.

## Stratégie de collecte et de modélisation

Le projet travaille à l'échelle des **12 régions métropolitaines** couvertes par les données éCO2mix (la Corse n'y figure pas). Le cœur du projet est le croisement de trois sources de données :

- **Consommation et production (ODRE, éCO2mix régional)** : consommation et production d'électricité par région et par filière, au pas de 30 minutes, depuis 2013. Le projet se concentre sur les filières renouvelables (éolien, solaire, hydraulique, bioénergies). Les autres filières (nucléaire, thermique fossile : gaz, charbon, fioul) figurent dans les mêmes données et pourront être exploitées dans une future version.

- **Parc de production (ODRE, registre national des installations)** : installations de production d'électricité avec leur filière, leur puissance installée, leur commune et leur date de mise en service.

- **Météo (Open-Meteo)** : Open-Meteo fournit des séries météo horaires en des points géographiques (latitude, longitude), sans notion de région. Je relève donc la météo au centre de chaque département, puis je calcule une moyenne régionale **pondérée selon ce que chaque variable doit expliquer** :
  - la température à 2 m, pondérée par la **population** (on consomme là où l'on habite), sert à expliquer la consommation et à calculer les DJU ;
  - la vitesse du vent à 100 m (hauteur des nacelles d'éoliennes), pondérée par la **puissance éolienne installée** ;
  - le rayonnement solaire, pondéré par la **puissance solaire installée** ;
  - les précipitations et la neige, pondérées par la **puissance hydraulique installée**, et cumulées sur plusieurs semaines.

  API gratuite, sans clé, données historiques disponibles depuis 1940.


# Démarrage

```
cp .env.example .env    # puis renseigner ses propres valeurs
docker compose up -d
```

Lance RustFS, PostgreSQL et Polaris, puis crée le bucket et le catalogue Iceberg.


# Avancement

- [Feuille de route](docs/feuille_de_route.md) : étapes de construction et outils utilisés.
- [Journal de bord](docs/JOURNAL.md) : avancement au fil de l'eau, difficultés rencontrées et décisions prises.


# Les données

Les données se trouvent ici :

- [éCO2mix régional, consolidé et définitif (ODRE)](https://odre.opendatasoft.com/explore/dataset/eco2mix-regional-cons-def/)
- [éCO2mix régional, temps réel (ODRE)](https://odre.opendatasoft.com/explore/dataset/eco2mix-regional-tr/)
- [Registre national des installations de production et de stockage d'électricité (ODRE)](https://odre.opendatasoft.com/explore/dataset/registre-national-installation-production-stockage-electricite-agrege-311225/)
- [Open-Meteo, API météo historique (gratuit, sans clé API)](https://open-meteo.com/en/docs/historical-weather-api)
- [Agence ORE](https://portail.agenceore.fr/pages/explore) (consommation par secteur, pour une future version)
- [Hub'Eau, API hydrométrie](https://hubeau.eaufrance.fr/page/api-hydrometrie) (débits des rivières, pour une future version)
