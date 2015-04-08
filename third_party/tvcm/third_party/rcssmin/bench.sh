#!/bin/bash
#  Copyright 2011 - 2014
#  Andr\xe9 Malo or his licensors, as applicable

#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
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
