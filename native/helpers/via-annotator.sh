#!/usr/bin/env bash
set -euo pipefail

readonly VIA_VERSION='3.0.13'
readonly VIA_ASSET_DIR='/opt/via-annotator'
readonly VIA_ASSET_NAME='via_image_annotator.html'
readonly VIA_ASSET_SHA256='44de1edcee45a0c442dcd028316cdce1647b4fb1a3ca3669b07cd77f39e5fc98'
readonly DEFAULT_PORT='8765'

usage() {
    cat <<'EOF'
Usage:
  via-annotator --help
  via-annotator --version
  via-annotator --check
  via-annotator [--port PORT]

Serve the installed VGG Image Annotator standalone application locally.
The server runs in the foreground, binds only to 127.0.0.1, and defaults
to port 8765. Press Ctrl+C to stop it.
EOF
}

check_installation() {
    local asset_path="${VIA_ASSET_DIR}/${VIA_ASSET_NAME}"

    if [[ ! -f "${asset_path}" ]]; then
        printf 'VIA asset is missing: %s\n' "${asset_path}" >&2
        return 1
    fi

    if [[ ! -f "${VIA_ASSET_DIR}/LICENSE" ]]; then
        printf 'VIA license is missing: %s\n' "${VIA_ASSET_DIR}/LICENSE" >&2
        return 1
    fi

    printf '%s  %s\n' "${VIA_ASSET_SHA256}" "${asset_path}" | sha256sum -c -
    printf 'VIA Annotator %s installation is valid.\n' "${VIA_VERSION}"
}

validate_port() {
    local port="$1"

    if [[ ! "${port}" =~ ^[0-9]{1,5}$ ]] ||
        ((10#${port} < 1 || 10#${port} > 65535)); then
        printf 'Invalid port: %s (expected an integer from 1 to 65535)\n' "${port}" >&2
        return 1
    fi
}

port="${DEFAULT_PORT}"
case "${1:-}" in
    '')
        if (($# != 0)); then
            usage >&2
            exit 2
        fi
        ;;
    --help|-h)
        if (($# != 1)); then
            usage >&2
            exit 2
        fi
        usage
        exit 0
        ;;
    --version)
        if (($# != 1)); then
            usage >&2
            exit 2
        fi
        printf 'via-annotator %s\n' "${VIA_VERSION}"
        exit 0
        ;;
    --check)
        if (($# != 1)); then
            usage >&2
            exit 2
        fi
        check_installation
        exit 0
        ;;
    --port)
        if (($# != 2)); then
            usage >&2
            exit 2
        fi
        port="$2"
        ;;
    *)
        printf 'Unknown option: %s\n' "$1" >&2
        usage >&2
        exit 2
        ;;
esac

validate_port "${port}"
check_installation

readonly local_url="http://127.0.0.1:${port}/${VIA_ASSET_NAME}"
printf 'VIA Annotator %s is available at %s\n' "${VIA_VERSION}" "${local_url}"
printf 'Press Ctrl+C to stop the server.\n'

exec python3 -m http.server "${port}" \
    --bind 127.0.0.1 \
    --directory "${VIA_ASSET_DIR}"
