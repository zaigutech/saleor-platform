from __future__ import annotations

import json
import logging
import os
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger("dummy-payment-app")

APP_ID = os.environ.get("DUMMY_PAYMENT_APP_ID", "saleor.io.dummy-payment-app")
APP_NAME = os.environ.get("DUMMY_PAYMENT_APP_NAME", "Dummy Payment App")
APP_VERSION = os.environ.get("DUMMY_PAYMENT_APP_VERSION", "1.0.0")
PUBLIC_URL = os.environ.get(
    "DUMMY_PAYMENT_APP_PUBLIC_URL", "http://dummy-payment-app.local:3000"
).rstrip("/")
PORT = int(os.environ.get("PORT", "3000"))

SUBSCRIPTION_QUERY = """subscription {
  event {
    ... on TransactionInitializeSession {
      data
      action { amount currency actionType }
    }
    ... on TransactionProcessSession {
      data
      action { amount currency actionType }
    }
    ... on PaymentGatewayInitializeSession {
      data
      amount
    }
  }
}"""

SYNC_EVENTS = [
    "PAYMENT_GATEWAY_INITIALIZE_SESSION",
    "TRANSACTION_INITIALIZE_SESSION",
    "TRANSACTION_PROCESS_SESSION",
]

MANIFEST = {
    "id": APP_ID,
    "name": APP_NAME,
    "version": APP_VERSION,
    "about": "Local dummy payment gateway for testing Saleor's Transactions API.",
    "permissions": ["HANDLE_PAYMENTS"],
    "appUrl": f"{PUBLIC_URL}/",
    "tokenTargetUrl": f"{PUBLIC_URL}/api/register",
    "webhooks": [
        {
            "name": f"{APP_NAME} transaction session",
            "targetUrl": f"{PUBLIC_URL}/api/webhooks",
            "query": SUBSCRIPTION_QUERY,
            "isActive": True,
            "syncEvents": SYNC_EVENTS,
        }
    ],
}

ACTIONS_BY_RESULT = {
    "CHARGE_SUCCESS": ["REFUND", "CANCEL"],
    "CHARGE_REQUEST": ["REFUND", "CANCEL"],
    "AUTHORIZATION_SUCCESS": ["CHARGE", "CANCEL"],
    "AUTHORIZATION_REQUEST": ["CHARGE", "CANCEL"],
}

# Results accepted by Saleor's TransactionSession* response schemas.
SUPPORTED_RESULTS = set(ACTIONS_BY_RESULT) | {
    "CHARGE_FAILURE",
    "AUTHORIZATION_FAILURE",
    "CHARGE_ACTION_REQUIRED",
    "AUTHORIZATION_ACTION_REQUIRED",
    "CANCEL_SUCCESS",
}

# actionType (as sent by Saleor) -> result this dummy gateway reports back.
RESULT_BY_ACTION_TYPE = {
    "CHARGE": "CHARGE_SUCCESS",
    "AUTHORIZATION": "AUTHORIZATION_SUCCESS",
    "CANCEL": "CANCEL_SUCCESS",
    "REFUND": "REFUND_SUCCESS",
}

DEFAULT_RESULT = "CHARGE_SUCCESS"

INDEX_HTML = """<!doctype html>
<html lang="en">
<meta charset="utf-8">
<title>{name}</title>
<style>
  body {{ font: 14px/1.6 ui-monospace, SFMono-Regular, Menlo, monospace; margin: 3rem auto; max-width: 44rem; padding: 0 1rem; color: #111; }}
  h1 {{ font-size: 1.25rem; }}
  code {{ background: #f2f2f2; padding: 0.1rem 0.3rem; border-radius: 3px; }}
  li {{ margin: 0.35rem 0; }}
</style>
<h1>{name}</h1>
<p>Saleor payment app (<code>{app_id}</code>) running locally.</p>
<ul>
  <li><code>GET /api/manifest</code> &mdash; app manifest</li>
  <li><code>POST /api/register</code> &mdash; token exchange target</li>
  <li><code>POST /api/webhooks</code> &mdash; sync payment webhooks</li>
  <li><code>GET /healthz</code> &mdash; liveness probe</li>
</ul>
</html>
""".format(name=APP_NAME, app_id=APP_ID)


def get_event(payload: dict) -> dict:
    """Normalize a Saleor subscription payload.

    Saleor runs the subscription root field ``event`` and then unwraps it, so the
    payload we receive is a flat dict of the selected field names (``data``,
    ``action``, ``amount``, ...). Fall back to the wrapped shape just in case.
    """
    if not isinstance(payload, dict):
        return {}
    if any(k in payload for k in ("data", "action", "amount")):
        return payload
    inner = payload.get("event")
    return inner if isinstance(inner, dict) else {}


def pick_result(payload: dict) -> str:
    """Pick the result to report: caller hint first, then the requested action."""
    event = get_event(payload)
    data = event.get("data")
    if isinstance(data, dict):
        hint = data.get("event") or {}
        if isinstance(hint, dict):
            requested = str(hint.get("type") or "").upper()
            if requested in SUPPORTED_RESULTS:
                return requested
        requested = str(data.get("type") or "").upper()
        if requested in SUPPORTED_RESULTS:
            return requested
    action = event.get("action") or {}
    action_type = str(action.get("actionType") or "").upper()
    result = RESULT_BY_ACTION_TYPE.get(action_type, DEFAULT_RESULT)
    return result if result in SUPPORTED_RESULTS else DEFAULT_RESULT


def build_transaction_response(payload: dict) -> dict:
    result = pick_result(payload)
    response = {
        "result": result,
        "pspReference": str(uuid.uuid4()),
        "message": f"Dummy payment {result.replace('_', ' ').lower()}",
    }
    if result in ACTIONS_BY_RESULT:
        response["actions"] = ACTIONS_BY_RESULT[result]
    return response


def build_gateway_initialize_response(payload: dict) -> dict:
    """Echo back whatever config the frontend asked to store on the gateway."""
    event = get_event(payload)
    data = event.get("data")
    return {"data": data if data is not None else {}}


def dispatch_webhook(event: str | None, payload: dict) -> dict:
    if event == "PAYMENT_GATEWAY_INITIALIZE_SESSION":
        return build_gateway_initialize_response(payload)
    if event in ("TRANSACTION_INITIALIZE_SESSION", "TRANSACTION_PROCESS_SESSION"):
        return build_transaction_response(payload)
    if get_event(payload).get("action"):
        return build_transaction_response(payload)
    return build_gateway_initialize_response(payload)


class Handler(BaseHTTPRequestHandler):
    server_version = "SaleorDummyPaymentApp"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        logger.info("%s %s", self.address_string(), fmt % args)

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, body: str, status=200):
        raw = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length > 0 else b""
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self._send_html(INDEX_HTML)
        elif path == "/healthz":
            self._send_json({"status": "ok", "appId": APP_ID})
        elif path == "/api/manifest":
            self._send_json(MANIFEST)
        else:
            self._send_json({"error": "not found"}, status=404)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/register":
            payload = self._read_json()
            token = payload.get("auth_token")
            logger.info("token exchange, received token=%s", bool(token))
            self._send_json({"ok": True})
            return
        if path == "/api/webhooks":
            event = self.headers.get("Saleor-Event") or self.headers.get(
                "X-Saleor-Event"
            )
            payload = self._read_json()
            logger.info("webhook %s payload=%s", event, json.dumps(payload)[:600])
            self._send_json(dispatch_webhook(event, payload))
            return
        self._send_json({"error": "not found"}, status=404)


def main():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    logger.info(
        "%s (%s) listening on :%s publicUrl=%s", APP_NAME, APP_ID, PORT, PUBLIC_URL
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
