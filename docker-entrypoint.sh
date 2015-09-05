#!/bin/bash
set -e

if [ "$1" = 'gunicorn' ]; then
    chown -R ganttchart .
    exec gosu ganttchart "$@"
fi

exec "$@"
