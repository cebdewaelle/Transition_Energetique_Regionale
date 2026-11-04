#!/bin/bash
#
# Connexion de ClickHouse au catalogue Polaris, inspirée du guide officiel de ClickHouse :
# https://github.com/ClickHouse/ClickHouse/blob/fb4661a3478a/docs/guides/use-cases/data-warehousing/polaris-catalog.mdx
#
set -e

clickhouse-client --user "$CLICKHOUSE_USER" --password "$CLICKHOUSE_PASSWORD" --multiquery <<SQL
SET allow_database_iceberg = 1;
CREATE DATABASE IF NOT EXISTS polaris
ENGINE = DataLakeCatalog('http://polaris:8181/api/catalog/v1')
SETTINGS
    catalog_type = 'rest',
    warehouse = '$CATALOG_NAME',
    catalog_credential = '$POLARIS_ADMIN_CLIENT_ID:$POLARIS_ADMIN_CREDENTIALS',
    auth_scope = 'PRINCIPAL_ROLE:ALL',
    oauth_server_uri = 'http://polaris:8181/api/catalog/v1/oauth/tokens',
    storage_endpoint = 'http://rustfs:9000/$BUCKET_NAME',
    vended_credentials = 0,
    aws_access_key_id = '$RUSTFS_ACCESS_KEY',
    aws_secret_access_key = '$RUSTFS_SECRET_KEY';
SQL
