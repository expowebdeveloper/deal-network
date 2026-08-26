#!/bin/sh
# Bring the schema up to date before serving.
#
# The application used to call create_all() on boot, which meant a fresh volume
# got its tables for free. Alembic owns the schema now, so that step has to
# happen here instead — compose already waits for the database to be healthy,
# so this runs against a database that is accepting connections.
set -e

echo "entrypoint: alembic upgrade head"
alembic upgrade head

exec "$@"
