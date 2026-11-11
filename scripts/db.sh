#!/usr/bin/env bash
# Local PostgreSQL 18 + pgvector without Docker (pixi env). Usage: scripts/db.sh start|stop
set -e
cd "$(dirname "$0")/.."
export PIXI_HOME=${PIXI_HOME:-$HOME/workspace/.tools/pixi} PIXI_CACHE_DIR=${PIXI_CACHE_DIR:-$HOME/workspace/.tools/pixi-cache}
D=.pgdata
case "$1" in
  start)
    [ -d $D ] || { pixi run initdb -D $D -U postgres -A trust >/dev/null; }
    pixi run pg_ctl -D $D -l .pgdata.log -o "-p 5433 -k /tmp" start
    sleep 2
    pixi run psql -h localhost -p 5433 -U postgres -tc "SELECT 1 FROM pg_database WHERE datname='md510k'" | grep -q 1 || pixi run createdb -h localhost -p 5433 -U postgres md510k
    ;;
  stop) pixi run pg_ctl -D $D stop ;;
esac
