#!/bin/sh
set -e

# При пустой базе — заливаем историю из файла diary (см. scripts/ensure_data.py)
python scripts/ensure_data.py || true

exec "$@"
