#!/bin/bash
set -e

if [ "$1" = 'ganttcharts-backup.sh' ]; then
    chown -R ganttcharts .
    exec gosu ganttcharts "$@"
fi

exec "$@"
