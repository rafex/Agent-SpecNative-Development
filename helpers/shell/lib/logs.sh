#!/usr/bin/env bash

resolve_log_file() {
    local requested="$1"
    local project_name="$2"
    local timestamp

    if [[ -n "$requested" ]]; then
        if mkdir -p "$(dirname "$requested")" 2>/dev/null && [[ -w "$(dirname "$requested")" ]]; then
            printf '%s\n' "$requested"
            return 0
        fi
    fi

    timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
    requested="${TMPDIR:-/tmp}/$project_name/log-pilot-$timestamp.log"
    mkdir -p "$(dirname "$requested")"
    printf '%s\n' "$requested"
}

init_log() {
    local log_file="$1"
    exec > >(tee -a "$log_file") 2>&1
}
