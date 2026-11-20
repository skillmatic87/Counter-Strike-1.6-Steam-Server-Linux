#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if ! command -v python3 >/dev/null || ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
    echo 'Python 3.10+ is required. Install it with: sudo apt install python3' >&2
    exit 1
fi
exec python3 "$project_dir/scripts/install_cs16_linux.py" "$@"
