#!/bin/sh
# Container entrypoint for IOFlow.
#
# SECRET_KEY (signs login tokens) and ENCRYPTION_KEY (encrypts stored
# credentials) must stay the same across restarts. When they are not passed
# in as environment variables, generate them once and keep them in
# $IOFLOW_SECRETS_DIR, which docker-compose.yml mounts as a named volume.
set -e

SECRETS_DIR="${IOFLOW_SECRETS_DIR:-/var/lib/ioflow}"

fail() {
    echo "ioflow-entrypoint: ERROR: $1" >&2
    exit 1
}

# ensure_secret NAME PYTHON_SNIPPET_THAT_PRINTS_A_NEW_VALUE
ensure_secret() {
    name="$1"
    generator="$2"
    eval "current=\${$name:-}"
    if [ -n "$current" ]; then
        return 0
    fi

    file="$SECRETS_DIR/$name"
    if [ ! -s "$file" ]; then
        mkdir -p "$SECRETS_DIR" 2>/dev/null \
            || fail "cannot create $SECRETS_DIR; set $name yourself or mount a writable volume there"
        ( umask 077 && python -c "$generator" > "$file" ) \
            || { rm -f "$file"; fail "could not generate $name; set it as an environment variable"; }
        echo "ioflow-entrypoint: generated $name and stored it in $file"
    fi

    value="$(cat "$file")"
    [ -n "$value" ] || fail "$file is empty; delete it or set $name yourself"
    export "$name=$value"
}

ensure_secret SECRET_KEY "import secrets; print(secrets.token_urlsafe(48))"
ensure_secret ENCRYPTION_KEY "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

exec "$@"
