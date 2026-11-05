#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
server_dir="${1:-$project_dir/CS16Server-Linux}"
if (( $# > 0 )); then shift; fi
if [[ ! -f "$server_dir/Start-CS16.sh" || ! -f "$server_dir/hlds_linux" ]]; then
    echo 'Installed server not found. Run bash Setup-Linux.sh first, or supply its folder.' >&2
    exit 1
fi
exec bash "$server_dir/Start-CS16.sh" "$@"
