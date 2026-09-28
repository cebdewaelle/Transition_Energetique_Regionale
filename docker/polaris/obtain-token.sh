#!/bin/sh
#
# La base de ce obtain-token.sh est inspirée de l'exemple officiel de Polaris, disponible sur GitHub :
# https://github.com/apache/polaris/blob/95bc59bb3dd2/site/content/guides/assets/polaris/obtain-token.sh
# (licence Apache 2.0)
#

set -e

apk add --no-cache jq

realm=${1:-"POLARIS"}

TOKEN=$(curl \
  --fail-with-body \
  -s \
  http://polaris:8181/api/catalog/v1/oauth/tokens \
  --user ${CLIENT_ID}:${CLIENT_SECRET} \
  -H "Polaris-Realm: $realm" \
  -d grant_type=client_credentials \
  -d scope=PRINCIPAL_ROLE:ALL | jq -r .access_token)

if [ -z "${TOKEN}" ]; then
  echo "Failed to obtain access token."
  exit 1
fi

export TOKEN
