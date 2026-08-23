#!/bin/sh
set -eu

input=${1:?usage: run-ppstructure-smoke.sh /absolute/input.png /absolute/output-dir [physical-page]}
output=${2:?usage: run-ppstructure-smoke.sh /absolute/input.png /absolute/output-dir [physical-page]}
physical_page=${3:-1}
case "$input" in /*) ;; *) echo "input must be an absolute path" >&2; exit 2 ;; esac
case "$output" in /*) ;; *) echo "output must be an absolute path" >&2; exit 2 ;; esac
case "$input$output" in *,*) echo "paths cannot contain commas" >&2; exit 2 ;; esac
test -f "$input"
case "$physical_page" in *[!0-9]*|'') echo "physical page must be a positive integer" >&2; exit 2 ;; esac
test "$physical_page" -gt 0 || { echo "physical page must be a positive integer" >&2; exit 2; }
test "$output" != / || { echo "output cannot be /" >&2; exit 2; }
mkdir -p "$output"
resolved_output=$(cd "$output" && pwd -P)
test "$output" = "$resolved_output" || { echo "output must be a canonical non-symlink path" >&2; exit 2; }
name=$(basename "$input")
uid=$(id -u)
gid=$(id -g)
test "$uid" -ne 0 || { echo "refusing to run the OCR process as root" >&2; exit 2; }
staging=$(mktemp -d)
trap 'rm -rf "$staging"' 0
memory=${NPL_PPSTRUCTURE_MEMORY:-6g}

docker run --rm --platform linux/amd64 --network none --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,noexec,mode=1777,size=256m \
  --tmpfs /opt/paddlex/temp:rw,nosuid,nodev,noexec,mode=1777,size=256m \
  --memory "$memory" --cpus 2 --pids-limit 256 --cap-drop ALL \
  --security-opt no-new-privileges --user "$uid:$gid" \
  --env PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT=False \
  --env NPL_PPSTRUCTURE_PHYSICAL_PAGE="$physical_page" \
  --mount "type=bind,src=$input,dst=/input/$name,readonly" \
  --mount "type=bind,src=$staging,dst=/output" \
  npl-ppstructure:local "/input/$name"

for result in "$staging"/*.json "$staging"/tables.jsonl; do
  test -f "$result" || continue
  target="$resolved_output/$(basename "$result")"
  test ! -e "$target" || { echo "refusing to overwrite $target" >&2; exit 1; }
  cp "$result" "$target"
done
