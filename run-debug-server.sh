#!/bin/sh
set -eu

if [ "$#" -eq 0 ]; then
  set -- /usr/bin/flask --debug run
fi

exec podman run --rm -it --network=host \
                --volume=moerderspiel-debug-data:/data --volume=moerderspiel-debug-cache:/cache \
                --env=BASE_URL=http://127.0.0.1:8000 --env=SECRET_KEY=debug \
                --env=FLASK_RUN_PORT=8000 --env=FLASK_APP=moerderspiel.web:app \
                --volume="$(dirname "$(readlink -f "$0")")":/opt/moerderspiel:ro \
                moerderspiel "$@"