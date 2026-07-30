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
readonly EXIT_NSS_TRUST=15

LOCAL_COPY=""
SYSTEM_TEMP=""
NSS_PASSWORD_FILE=""

cleanup() {
    if [ -n "$LOCAL_COPY" ]; then
        rm -f "$LOCAL_COPY"
    fi
    if [ -n "$SYSTEM_TEMP" ]; then
        sudo -n rm -f "$SYSTEM_TEMP" >/dev/null 2>&1 || true
    fi
    if [ -n "$NSS_PASSWORD_FILE" ]; then
        rm -f "$NSS_PASSWORD_FILE"
    fi
}
trap cleanup EXIT

fail() {
    local exit_code="$1"
    shift

    echo "[ERROR] $*" >&2
    exit "$exit_code"
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

nss_certificate_fingerprint() {
    local exported_certificate
    exported_certificate="$(mktemp)"

    if ! certutil -L -d "$NSS_DB" -n "$NSS_NICKNAME" -a >"$exported_certificate" 2>/dev/null; then
        rm -f "$exported_certificate"
        return 1
    fi

    certificate_fingerprint "$exported_certificate"
    rm -f "$exported_certificate"
}

nss_trust_flags() {
    certutil -L -d "$NSS_DB" 2>/dev/null \
        | awk -v nickname="$NSS_NICKNAME" 'index($0, nickname) == 1 { print $NF; exit }'
}

if ! command -v openssl >/dev/null 2>&1; then
    fail "$EXIT_DEPENDENCY_MISSING" "OpenSSL is unavailable; rebuild the workspace devcontainer image."
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
    fail "$EXIT_PUBLICATION_INVALID" "Could not fingerprint the host-published Budget Analyzer local CA."
fi

for dependency in sudo install mv mktemp update-ca-certificates certutil; do
    if ! command -v "$dependency" >/dev/null 2>&1; then
        fail "$EXIT_DEPENDENCY_MISSING" "$dependency is unavailable; rebuild the workspace devcontainer image."
    fi
done

SYSTEM_CHANGED=false
if [ ! -r "$SYSTEM_CERT_FILE" ] \
    || [ "$(certificate_fingerprint "$SYSTEM_CERT_FILE")" != "$PUBLICATION_FINGERPRINT" ]; then
    LOCAL_COPY="$(mktemp)"
    if ! install -m 0644 "$PUBLICATION_FILE" "$LOCAL_COPY"; then
        fail "$EXIT_SYSTEM_TRUST" "Could not prepare the public CA for system trust installation."
    fi

    SYSTEM_TEMP="${SYSTEM_CERT_FILE}.tmp.$$"
    if ! sudo -n install -m 0644 "$LOCAL_COPY" "$SYSTEM_TEMP" \
        || ! sudo -n mv -f "$SYSTEM_TEMP" "$SYSTEM_CERT_FILE"; then
        sudo -n rm -f "$SYSTEM_TEMP" >/dev/null 2>&1 || true
        SYSTEM_TEMP=""
        fail "$EXIT_SYSTEM_TRUST" "Could not atomically install the public CA into the system trust store."
    fi
    SYSTEM_TEMP=""

    rm -f "$LOCAL_COPY"
    LOCAL_COPY=""

    SYSTEM_CHANGED=true
fi

SYSTEM_BUNDLE_STALE=false
if [ ! -r "$SYSTEM_BUNDLE" ] \
    || ! openssl verify -CAfile "$SYSTEM_BUNDLE" "$WILDCARD_CERT_FILE" >/dev/null 2>&1; then
    SYSTEM_BUNDLE_STALE=true
fi

if [ "$SYSTEM_CHANGED" = true ] || [ "$SYSTEM_BUNDLE_STALE" = true ]; then
    if ! sudo -n update-ca-certificates >/dev/null; then
        fail "$EXIT_SYSTEM_TRUST" "System CA bundle update failed."
    fi
fi

if [ ! -r "$SYSTEM_BUNDLE" ] \
    || ! openssl verify -CAfile "$SYSTEM_BUNDLE" "$WILDCARD_CERT_FILE" >/dev/null 2>&1; then
    fail "$EXIT_SYSTEM_TRUST" "Combined system CA bundle does not verify the local ingress certificate."
fi

if ! mkdir -p "$NSS_DB_DIR" || ! chmod 700 "$NSS_DB_DIR"; then
    fail "$EXIT_NSS_TRUST" "Could not create the Chromium NSS database directory."
fi

if [ ! -f "$NSS_DB_DIR/cert9.db" ] \
    && ! certutil -N -d "$NSS_DB" --empty-password >/dev/null 2>&1; then
    fail "$EXIT_NSS_TRUST" "Could not initialize the Chromium NSS database."
fi

NSS_PASSWORD_FILE="$(mktemp)" \
    || fail "$EXIT_NSS_TRUST" "Could not prepare non-interactive Chromium NSS access."
: >"$NSS_PASSWORD_FILE"

NSS_CHANGED=false
CURRENT_NSS_FINGERPRINT="$(nss_certificate_fingerprint || true)"
CURRENT_NSS_TRUST="$(nss_trust_flags)"
if [ "$CURRENT_NSS_FINGERPRINT" != "$PUBLICATION_FINGERPRINT" ] \
    || [ "$CURRENT_NSS_TRUST" != "C,," ]; then
    certutil -D -d "$NSS_DB" -n "$NSS_NICKNAME" -f "$NSS_PASSWORD_FILE" \
        >/dev/null 2>&1 || true
    if ! certutil -A -d "$NSS_DB" -n "$NSS_NICKNAME" -t "C,," \
        -i "$PUBLICATION_FILE" -f "$NSS_PASSWORD_FILE" >/dev/null 2>&1; then
        fail "$EXIT_NSS_TRUST" "Could not import the public CA into Chromium's NSS database."
    fi
    NSS_CHANGED=true
fi

if [ "$SYSTEM_CHANGED" = true ] || [ "$NSS_CHANGED" = true ]; then
    echo "[OK] Installed Budget Analyzer local CA trust (SHA256 $PUBLICATION_FINGERPRINT)."
else
    echo "[SKIP] Budget Analyzer local CA trust is already current (SHA256 $PUBLICATION_FINGERPRINT)."
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if command -v check-budget-analyzer-local-ca-trust >/dev/null 2>&1; then
    exec check-budget-analyzer-local-ca-trust
fi

exec "$SCRIPT_DIR/check-budget-analyzer-local-ca-trust.sh"
