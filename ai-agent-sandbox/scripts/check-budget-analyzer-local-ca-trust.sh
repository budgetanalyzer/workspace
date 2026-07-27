#!/bin/bash

set -u
set -o pipefail

readonly PUBLICATION_FILE="/workspace/orchestration/nginx/certs/k8s/_mkcert-rootCA.pem"
readonly WILDCARD_CERT_FILE="/workspace/orchestration/nginx/certs/k8s/_wildcard.budgetanalyzer.localhost.pem"
readonly SYSTEM_CERT_FILE="/usr/local/share/ca-certificates/budget-analyzer-local-mkcert.crt"
readonly SYSTEM_BUNDLE="/etc/ssl/certs/ca-certificates.crt"
readonly NSS_DB_DIR="$HOME/.pki/nssdb"
readonly NSS_DB="sql:$NSS_DB_DIR"
readonly NSS_NICKNAME="Budget Analyzer local mkcert CA"

readonly EXIT_PUBLICATION_MISSING=10
readonly EXIT_PUBLICATION_INVALID=11
readonly EXIT_DEPENDENCY_MISSING=12
readonly EXIT_SYSTEM_TRUST=13
readonly EXIT_PYTHON_BUNDLE=14
readonly EXIT_NSS_TRUST=15

STATUS=0
NSS_EXPORT=""

trap 'if [ -n "$NSS_EXPORT" ]; then rm -f "$NSS_EXPORT"; fi' EXIT

record_failure() {
    local exit_code="$1"
    shift

    echo "[ERROR] $*" >&2
    if [ "$STATUS" -eq 0 ]; then
        STATUS="$exit_code"
    fi
}

certificate_fingerprint() {
    openssl x509 -in "$1" -noout -sha256 -fingerprint 2>/dev/null \
        | sed -e 's/^[^=]*=//' -e 's/://g'
}

certificate_is_valid_ca() {
    openssl x509 -in "$1" -noout >/dev/null 2>&1 \
        && openssl x509 -in "$1" -noout -checkend 0 >/dev/null 2>&1 \
        && openssl x509 -in "$1" -noout -text 2>/dev/null | grep -q 'CA:TRUE'
}

nss_trust_flags() {
    certutil -L -d "$NSS_DB" 2>/dev/null \
        | awk -v nickname="$NSS_NICKNAME" 'index($0, nickname) == 1 { print $NF; exit }'
}

if ! command -v openssl >/dev/null 2>&1; then
    echo "[ERROR] OpenSSL is unavailable; rebuild the workspace devcontainer image." >&2
    exit "$EXIT_DEPENDENCY_MISSING"
fi

if [ ! -r "$PUBLICATION_FILE" ]; then
    echo "[ERROR] Host-published Budget Analyzer local CA is missing." >&2
    echo "        Run ./setup.sh from the orchestration checkout on the host, then retry." >&2
    exit "$EXIT_PUBLICATION_MISSING"
fi

if ! certificate_is_valid_ca "$PUBLICATION_FILE"; then
    echo "[ERROR] Host-published Budget Analyzer local CA is invalid or expired." >&2
    echo "        Run ./setup.sh from the orchestration checkout on the host, then retry." >&2
    exit "$EXIT_PUBLICATION_INVALID"
fi

if [ ! -r "$WILDCARD_CERT_FILE" ] \
    || ! openssl verify -CAfile "$PUBLICATION_FILE" "$WILDCARD_CERT_FILE" >/dev/null 2>&1; then
    echo "[ERROR] Host-published Budget Analyzer local CA does not verify the local ingress certificate." >&2
    echo "        Run ./setup.sh from the orchestration checkout on the host, then retry." >&2
    exit "$EXIT_PUBLICATION_INVALID"
fi

PUBLICATION_FINGERPRINT="$(certificate_fingerprint "$PUBLICATION_FILE")"
if [ -z "$PUBLICATION_FINGERPRINT" ]; then
    echo "[ERROR] Could not fingerprint the host-published Budget Analyzer local CA." >&2
    exit "$EXIT_PUBLICATION_INVALID"
fi

CERTUTIL_AVAILABLE=true
if ! command -v certutil >/dev/null 2>&1; then
    record_failure "$EXIT_DEPENDENCY_MISSING" "certutil is unavailable; rebuild the workspace devcontainer image."
    CERTUTIL_AVAILABLE=false
fi

if [ ! -r "$SYSTEM_CERT_FILE" ]; then
    record_failure "$EXIT_SYSTEM_TRUST" "System trust copy is missing."
elif [ "$(certificate_fingerprint "$SYSTEM_CERT_FILE")" != "$PUBLICATION_FINGERPRINT" ]; then
    record_failure "$EXIT_SYSTEM_TRUST" "System trust copy is stale."
fi

if [ ! -r "$SYSTEM_BUNDLE" ] \
    || ! openssl verify -CAfile "$SYSTEM_BUNDLE" "$WILDCARD_CERT_FILE" >/dev/null 2>&1; then
    record_failure "$EXIT_SYSTEM_TRUST" "Combined system CA bundle does not verify the local ingress certificate."
fi

if [ "${SSL_CERT_FILE:-}" != "$SYSTEM_BUNDLE" ]; then
    record_failure "$EXIT_PYTHON_BUNDLE" "Python HTTPS bundle is not configured as $SYSTEM_BUNDLE."
fi

if [ "$CERTUTIL_AVAILABLE" = false ]; then
    :
elif [ ! -f "$NSS_DB_DIR/cert9.db" ]; then
    record_failure "$EXIT_NSS_TRUST" "Chromium NSS database is missing."
else
    NSS_EXPORT="$(mktemp)"
    if ! certutil -L -d "$NSS_DB" -n "$NSS_NICKNAME" -a >"$NSS_EXPORT" 2>/dev/null; then
        record_failure "$EXIT_NSS_TRUST" "Chromium NSS trust entry is missing."
    elif [ "$(certificate_fingerprint "$NSS_EXPORT")" != "$PUBLICATION_FINGERPRINT" ]; then
        record_failure "$EXIT_NSS_TRUST" "Chromium NSS trust entry is stale."
    elif [ "$(nss_trust_flags)" != "C,," ]; then
        record_failure "$EXIT_NSS_TRUST" "Chromium NSS entry does not have CA trust flags."
    fi
fi

if [ "$STATUS" -eq 0 ]; then
    echo "[OK] Budget Analyzer local CA trust is current (SHA256 $PUBLICATION_FINGERPRINT)."
fi

exit "$STATUS"
