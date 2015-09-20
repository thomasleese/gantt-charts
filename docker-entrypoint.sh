#!/bin/bash
set -e

if [ "$1" = 'gunicorn' ]; then
    chown -R ganttcharts .
    exec gosu ganttcharts "$@"
fi

exec "$@"
