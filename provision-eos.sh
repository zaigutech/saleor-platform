#!/usr/bin/env bash
# Saleor provisioning for EOS: the non-shippable product types, the Services and ServicePackages categories, whose ids
# go to EOS, the OpenID Connect plugin and the EOS App with its order webhook, plus the Storefront App when
# STOREFRONT_ENV_FILE is set; only eos's dev-env sets it, since the storefront runs only in local development, as a
# reference for eweb's shop. Run once, against a fresh Saleor with its services up; a second run creates them all again.
# Deployment: docs/operations/deploy.md.
# Needs SALEOR_DASHBOARD_CLIENT_SECRET, which the keycloak repository's provision-eos.sh writes into .env; the
# environment overrides .env. In production also set COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml.
set -euo pipefail
cd "$(dirname "$0")"

CALLER_ENV=$(export -p)
set -a
[ ! -f .env ] || . ./.env
set +a
eval "$CALLER_ENV"

SALEOR_API_URL="${SALEOR_API_URL:-http://localhost:8000/graphql/}"
DASHBOARD_CLIENT_SECRET="${SALEOR_DASHBOARD_CLIENT_SECRET:?Set SALEOR_DASHBOARD_CLIENT_SECRET (the saleor-dashboard client secret in Keycloak)}"
# The browser reaches Keycloak at KEYCLOAK_PUBLIC_URL, Saleor's containers at KEYCLOAK_URL_FOR_SALEOR.
KEYCLOAK_PUBLIC_URL="${KEYCLOAK_PUBLIC_URL:-http://localhost:8081}"
KEYCLOAK_URL_FOR_SALEOR="${KEYCLOAK_URL_FOR_SALEOR:-http://172.17.0.1:8081}"
KEYCLOAK_REALM="${KEYCLOAK_REALM:-eos}"
EOS_ORDER_WEBHOOK_URL="${EOS_ORDER_WEBHOOK_URL:-http://172.20.0.1:8080/api/webhooks/saleor/order}"
# The .env files of sibling checkouts that receive the App tokens; a missing file gets the token printed.
EOS_ENV_FILE="${EOS_ENV_FILE:-../eos/.env}"
STOREFRONT_ENV_FILE="${STOREFRONT_ENV_FILE:-}"
PROVISIONING_APP="EOS provisioning"

manage() { docker compose exec -T saleor-api python3 manage.py "$@"; }
# create_app NAME [PERMISSION...]: creates an active App and prints its token, which Saleor shows only this once.
create_app() {
  local name=$1; shift
  manage create_app --activate "${@/#/--permission=}" "$name" | tail -n 1 | jq -r .auth_token
}
# graphql TOKEN FILE [JQ_ARG...]: sends graphql/FILE with the JQ_ARGs (--arg NAME VALUE, --rawfile NAME PATH) as its
# variables and prints the response's `data`; fails on any error, top-level or in a mutation's `errors`.
graphql() {
  local token=$1 file=$2; shift 2
  jq -n --rawfile operation "graphql/$file" "$@" '{query: $operation, variables: ($ARGS.named | del(.operation))}' \
    | curl -sS --fail-with-body -H "Authorization: Bearer $token" -H "Content-Type: application/json" -d @- "$SALEOR_API_URL" \
    | jq -c '[.errors[]?, (.data[]? | .errors[]?)] as $errors | if $errors == [] then .data else $errors | halt_error end'
}
# hand_over FILE KEY VALUE LABEL: sets KEY=VALUE in FILE (its KEY line, else a new line) or, without FILE, prints VALUE.
hand_over() {
  if [ ! -f "$1" ]; then echo "    $4 ($2; $1 not found): $3"; return; fi
  python3 -c '
import sys, pathlib
path, key, value = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
lines = path.read_text().splitlines()
at = next((i for i, line in enumerate(lines) if line.startswith(key + "=")), len(lines))
lines[at:at + 1] = [f"{key}={value}"]
path.write_text("\n".join(lines) + "\n")' "$1" "$2" "$3"
  echo "    $4 written to $1 as $2"
}

echo "==> Creating the '$PROVISIONING_APP' App, which sends the next three mutations and is then deactivated"
PROVISIONING_TOKEN=$(create_app "$PROVISIONING_APP" MANAGE_PRODUCT_TYPES_AND_ATTRIBUTES MANAGE_PRODUCTS MANAGE_PLUGINS)

echo "==> Creating the product types Non Shippable and Service"
graphql "$PROVISIONING_TOKEN" product-types.graphql > /dev/null

echo "==> Creating the categories Services and ServicePackages"
CATEGORIES=$(graphql "$PROVISIONING_TOKEN" categories.graphql)
hand_over "$EOS_ENV_FILE" EOS_SALEOR_CATEGORYSERVICE "$(jq -r .services.category.id <<<"$CATEGORIES")" "Services category id"
hand_over "$EOS_ENV_FILE" EOS_SALEOR_CATEGORYSERVICEPACKAGE "$(jq -r .servicePackages.category.id <<<"$CATEGORIES")" \
  "ServicePackages category id"

echo "==> Configuring the OpenID Connect plugin"
OIDC_URL="$KEYCLOAK_URL_FOR_SALEOR/realms/$KEYCLOAK_REALM/protocol/openid-connect"
graphql "$PROVISIONING_TOKEN" oidc-plugin.graphql --arg clientSecret "$DASHBOARD_CLIENT_SECRET" \
  --arg authorizationUrl "$KEYCLOAK_PUBLIC_URL/realms/$KEYCLOAK_REALM/protocol/openid-connect/auth" \
  --arg tokenUrl "$OIDC_URL/token" --arg jwksUrl "$OIDC_URL/certs" --arg userInfoUrl "$OIDC_URL/userinfo" > /dev/null

echo "==> Deactivating the '$PROVISIONING_APP' App"
for id in $(manage app_list | jq -r --arg name "$PROVISIONING_APP" 'select(.kind == "app" and .name == $name) | .id'); do
  manage app_set_active --id "$id" --active false
done

echo "==> Creating the EOS App and its order webhook"
# MANAGE_STAFF lets EOS find staff accounts that shop, such as the super admin: Saleor shows staff only to it.
EOS_TOKEN=$(create_app EOS MANAGE_ORDERS MANAGE_PRODUCTS MANAGE_USERS MANAGE_STAFF MANAGE_CHECKOUTS MANAGE_CHANNELS)
graphql "$EOS_TOKEN" eos-order-webhook.graphql --arg targetUrl "$EOS_ORDER_WEBHOOK_URL" \
  --rawfile query graphql/eos-order-payload.graphql > /dev/null
hand_over "$EOS_ENV_FILE" EOS_SALEOR_APPTOKEN "$EOS_TOKEN" "EOS App token"

if [ -n "$STOREFRONT_ENV_FILE" ]; then
  echo "==> Creating the Storefront App"
  # Needs no permission: channel.defaultCountry, from which the storefront bills checkouts that skip the address, is
  # visible only to Apps and staff.
  STOREFRONT_TOKEN=$(create_app Storefront)
  hand_over "$STOREFRONT_ENV_FILE" SALEOR_APP_TOKEN "$STOREFRONT_TOKEN" "Storefront App token"
fi

echo "==> Done. Restart EOS${STOREFRONT_ENV_FILE:+ and the storefront} to use the new tokens and ids."
