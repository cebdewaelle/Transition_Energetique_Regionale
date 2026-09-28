--
-- Repris de l'exemple officiel de Polaris, disponible sur GitHub :
-- https://github.com/apache/polaris/blob/75dd1bbe7ad2/site/content/guides/assets/postgres/create-polaris-schema.sql
-- (licence Apache 2.0)
--
-- Polaris ne crée pas ce schéma lui-même. Postgres exécute ce fichier une seule fois,
-- au premier démarrage, quand le volume de données est encore vide.
--

CREATE SCHEMA IF NOT EXISTS polaris_schema;
