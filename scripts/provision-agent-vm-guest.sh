#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
    cat <<'EOF'
Usage: provision-agent-vm-guest.sh --docker-user USER

Provision an Ubuntu 24.04 development VM with the guest-host tools required by
Budget Analyzer bootstrap and Tilt: Docker/Compose, Git, OpenSSL, ShellCheck,
NSS trust tools, Node.js 24/npm, and Azul Zulu JDK 25.

Run this reviewed script from a human-operated guest shell. It changes the guest
OS and adds USER to the guest docker group; reconnect after it succeeds.
EOF
}

die() {
    printf 'provision-agent-vm-guest: %s\n' "$*" >&2
    exit 1
}

docker_user=''
while (($#)); do
    case "$1" in
        --docker-user)
            (($# >= 2)) || die '--docker-user requires a value'
            docker_user=$2
            shift 2
            ;;
        --help|-h)
            (($# == 1)) || die '--help does not accept other arguments'
            usage
            exit 0
            ;;
        *) die "unknown argument: $1" ;;
    esac
done

[[ -n "$docker_user" ]] || die '--docker-user is required'
[[ "$docker_user" =~ ^[a-z_][a-z0-9_-]*[$]?$ ]] || die 'invalid guest user name'
[[ "$docker_user" != root ]] || die 'the Docker user must be an unprivileged guest account'
id "$docker_user" >/dev/null 2>&1 || die "guest user does not exist: $docker_user"
[[ -r /etc/os-release ]] || die '/etc/os-release is unavailable'
# shellcheck disable=SC1091
. /etc/os-release
[[ "${ID:-}" == ubuntu && "${VERSION_ID:-}" == 24.04 ]] \
    || die 'this script requires Ubuntu 24.04'

for command_name in curl gpg install sudo; do
    command -v "$command_name" >/dev/null 2>&1 || die "$command_name is required"
done

sudo apt-get update
sudo apt-get install -y \
    ca-certificates curl docker.io docker-compose-v2 git gnupg libnss3-tools \
    openssl shellcheck

sudo install -d -m 0755 /etc/apt/keyrings
prereq_dir=$(mktemp -d)
cleanup() {
    rm -rf -- "$prereq_dir"
}
trap cleanup EXIT

curl -fsSLo "$prereq_dir/nodesource.key" \
    https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key
gpg --batch --dearmor --output "$prereq_dir/nodesource.gpg" \
    "$prereq_dir/nodesource.key"
sudo install -m 0644 "$prereq_dir/nodesource.gpg" /etc/apt/keyrings/nodesource.gpg

curl -fsSLo "$prereq_dir/azul.key" https://repos.azul.com/azul-repo.key
gpg --batch --dearmor --output "$prereq_dir/azul.gpg" "$prereq_dir/azul.key"
sudo install -m 0644 "$prereq_dir/azul.gpg" /etc/apt/keyrings/azul.gpg

printf '%s\n' \
    'deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_24.x nodistro main' \
    | sudo tee /etc/apt/sources.list.d/nodesource.list >/dev/null
printf '%s\n' \
    'deb [signed-by=/etc/apt/keyrings/azul.gpg] https://repos.azul.com/zulu/deb stable main' \
    | sudo tee /etc/apt/sources.list.d/zulu.list >/dev/null

sudo apt-get update
sudo apt-get install -y nodejs zulu25-jdk
sudo systemctl enable --now docker
sudo usermod -aG docker "$docker_user"

sudo docker info --format '{{.DockerRootDir}}' | grep -qx /var/lib/docker \
    || die 'guest Docker data root is not /var/lib/docker'
git --version
openssl version
java_version=$(java -version 2>&1 | head -n 1)
java_major=$(sed -n 's/^[^"]*"\([0-9][0-9]*\).*/\1/p' <<<"$java_version")
[[ "$java_major" == 25 ]] || die "expected JDK 25, got: $java_version"
printf '%s\n' "$java_version"
node_version=$(node --version)
[[ "$node_version" =~ ^v24\. ]] || die "expected Node.js 24, got: $node_version"
printf '%s\n' "$node_version"
npm_version=$(npm --version)
[[ "${npm_version%%.*}" =~ ^[0-9]+$ && "${npm_version%%.*}" -ge 10 ]] \
    || die "expected npm 10 or newer, got: $npm_version"
printf '%s\n' "$npm_version"
docker --version
docker compose version
certutil -H >/dev/null 2>&1

printf 'Guest prerequisites are installed. End this session and reconnect as %s.\n' \
    "$docker_user"
