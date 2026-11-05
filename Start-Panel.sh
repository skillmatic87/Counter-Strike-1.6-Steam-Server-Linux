#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if ! command -v python3 >/dev/null || ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
    echo 'Python 3.10+ is required.' >&2
    exit 1
fi
if (( $# > 1 )); then echo 'Usage: bash Start-Panel.sh [/path/to/server]' >&2; exit 1; fi
server_dir="${1:-$project_dir/CS16Server-Linux}"
if [[ -f "$server_dir/Start-CS16.sh" ]]; then
    exec python3 "$project_dir/scripts/server_panel.py" --server "$server_dir" --open-browser
elif (( $# > 0 )); then
    echo 'Installed server not found in the selected folder.' >&2
    exit 1
else
    exec python3 "$project_dir/scripts/server_panel.py" --open-browser
fi
