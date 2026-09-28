#!/bin/sh
#
# La base de ce create-catalog.sh est inspirée de l'exemple officiel de Polaris, disponible sur GitHub :
# https://github.com/apache/polaris/blob/95bc59bb3dd2/site/content/guides/assets/polaris/create-catalog.sh
# (licence Apache 2.0)
#


set -e

apk add --no-cache jq

realm=${1:-"POLARIS"}

TOKEN=${2:-""}

BASEDIR=$(dirname $0)

if [ -z "$TOKEN" ]; then
  source $BASEDIR/obtain-token.sh
fi

echo
echo "Obtained access token"

# Idempotence : avec la persistance Postgres, le catalogue survit aux redémarrages.
# 200 = il existe déjà, 404 = à créer, tout autre code = état inattendu, on s'arrête.
STATUS=$(curl -s -o /dev/null -w '%{http_code}' \
   -H "Authorization: Bearer ${TOKEN}" \
   -H "Polaris-Realm: $realm" \
   "http://polaris:8181/api/management/v1/catalogs/$CATALOG_NAME")

case "$STATUS" in
  200)
    echo "Catalog $CATALOG_NAME already exists in realm $realm, skipping creation."
    exit 0
    ;;
  404)
    ;;
  *)
    echo "Unexpected HTTP status $STATUS while checking catalog $CATALOG_NAME." >&2
    exit 1
    ;;
esac

STORAGE_TYPE="FILE"
if [ -z "${STORAGE_LOCATION}" ]; then
    echo "STORAGE_LOCATION is not set, using FILE storage type"
    STORAGE_LOCATION="file:///var/tmp/$CATALOG_NAME/"
else
    echo "STORAGE_LOCATION is set to '$STORAGE_LOCATION'"
    if [[ "$STORAGE_LOCATION" == s3* ]]; then
        STORAGE_TYPE="S3"
    elif [[ "$STORAGE_LOCATION" == gs* ]]; then
        STORAGE_TYPE="GCS"
    else
        STORAGE_TYPE="AZURE"
    fi
    echo "Using StorageType: $STORAGE_TYPE"
fi

if [ -z "${STORAGE_CONFIG_INFO}" ]; then
    STORAGE_CONFIG_INFO="{\"storageType\": \"$STORAGE_TYPE\", \"allowedLocations\": [\"$STORAGE_LOCATION\"]}"

    if [[ "$STORAGE_TYPE" == "S3" ]]; then
        STORAGE_CONFIG_INFO=$(echo "$STORAGE_CONFIG_INFO" | jq --arg roleArn "$AWS_ROLE_ARN" '. + {roleArn: $roleArn}')
    elif [[ "$STORAGE_TYPE" == "AZURE" ]]; then
        STORAGE_CONFIG_INFO=$(echo "$STORAGE_CONFIG_INFO" | jq --arg tenantId "$AZURE_TENANT_ID" '. + {tenantId: $tenantId}')
    fi
fi

echo
echo Creating a catalog named $CATALOG_NAME in realm $realm...

PAYLOAD='{
   "catalog": {
     "name": "'$CATALOG_NAME'",
     "type": "INTERNAL",
     "readOnly": false,
     "properties": {
       "default-base-location": "'$STORAGE_LOCATION'"
     },
     "storageConfigInfo": '$STORAGE_CONFIG_INFO'
   }
 }'

echo $PAYLOAD

curl --fail-with-body \
   -s \
   -H "Authorization: Bearer ${TOKEN}" \
   -H 'Accept: application/json' \
   -H 'Content-Type: application/json' \
   -H "Polaris-Realm: $realm" \
   http://polaris:8181/api/management/v1/catalogs \
   -d "$PAYLOAD"

echo
echo Done.
