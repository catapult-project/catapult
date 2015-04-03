#!/bin/bash
set -e

export PYTHONPATH=$PWD
cleanup() {
    rm -f -- "$out"
}
out="$(mktemp)"
trap cleanup EXIT

for v in 3.4 3.3 3.2 3.1 3.0 2.7 2.6 2.5 2.4; do
(
    set -e

    p=python$v
    $p make.py makefile || continue
    CFLAGS=-O3 make clean compile
    $p -OO bench/main.py -p >( cat - >>"$out" ) bench/*.css
)
done
python make.py makefile

[ "$1" = "-w" ] && \
    python -mbench.write \
    -p docs/BENCHMARKS \
    <"$out" \
    || true
