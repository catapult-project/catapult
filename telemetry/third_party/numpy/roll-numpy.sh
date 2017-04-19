#!/bin/bash
# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# Script to download and package numpy for upload to Cloud Storage

workspace=

rm -rf lib
mkdir -p lib
cd lib
startdir=$PWD

fail() {
    cd "$startdir" &&
    rm -rf "$workspace"
    echo "$1"
    exit 1
}

ver=$1
if [ -z "$ver" ] ; then
    cat << EOF
Usage: $0 NUMPY_VERSION
 e.g.: $0 1.11.3

 Downloads numpy via pip, then produces a result for upload to Cloud Storage.

 numpy releases: https://github.com/numpy/numpy/tree/master/doc/release
 See telemetry/telemetry/internal/util/external_modules.py for version support.
EOF
    exit 1
fi

which -s virtualenv ||
    fail "virtualenv not found (sudo easy_install virtualenv)"

workspace=$(mktemp -d)
cd "$workspace"
virtualenv env
(
    cd env
    . bin/activate
    pip install "numpy==$ver"
)

rm -f "$startdir"/numpy.zip
rm -rf "$startdir"/numpy_*/
cd "env/lib/python2.7/site-packages"
zip -r "$startdir/numpy.zip" numpy

cd "$startdir/lib" &&
rm -rf "$workspace"

cat << EOF

========

The result was saved at ./numpy.zip

Now, from the catapult root directory, run:

dependency_manager/bin/update \\
  --config telemetry/telemetry/internal/binary_dependencies.json \\
  --dependency numpy \\
  --path PATH/TO/numpy.zip \\
  --platform PLATFORM

where PATH/TO/numpy.zip is the file path of numpy.zip, and PLATFORM is the
current platform string, e.g. mac_x86_64 or win_AMD64.
EOF
