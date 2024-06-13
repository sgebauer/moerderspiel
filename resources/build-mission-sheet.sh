#!/bin/sh
set -eu

# Check that all required parameters are set
: "${gameid?}" "${missioncode?}" "${owner?}" "${victim?}" "${gameurl?}" "${headline?}" "${destfile?}"

readonly sourcefile="$(readlink -f "$(dirname "$0")/mission.tex")"
readonly tempdir="$(mktemp -d)"
trap "rm -rf '$tempdir'" EXIT

cd "$tempdir"
latexmk -silent -pdf "$sourcefile"
install -D "$tempdir/mission.pdf" "$destfile"
