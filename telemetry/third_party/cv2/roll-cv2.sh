#!/bin/bash
# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# Script to build and package OpenCV for upload to Cloud Storage.

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
Usage: $0 OPENCV_VERSION
 e.g.: $0 2.4.13.2

 Downloads+builds OpenCV, then produces a result for upload to Cloud Storage.

 OpenCV releases: https://github.com/opencv/opencv/releases
 See telemetry/telemetry/internal/util/external_modules.py for version support.
EOF
    exit 1
fi

workspace=$(mktemp -d)
cd "$workspace"

curl "https://codeload.github.com/opencv/opencv/tar.gz/$ver" | tar x
cd "opencv-$ver/" ||
    fail "Didn't find opencv-$ver/ after extracting source tarball"
mkdir install
mkdir build
cd build
# BUILD_SHARED_LIBS=OFF           - Build a statically linked .so instead of
#                                   a .so that dynamically links .dylibs.
# CMAKE_INSTALL_PREFIX=../install - Install to a local directory.
cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_SHARED_LIBS=OFF \
    -DCMAKE_INSTALL_PREFIX=../install
make -j8 install # build and install

rm -f "$startdir"/cv2.zip
rm -rf "$startdir"/cv2_*/
cd "../install/lib/python2.7/site-packages/"
zip "$startdir/cv2.zip" cv2.so

cd "$startdir" &&
rm -rf "$workspace"

cat << EOF

========

The result was saved at ./cv2.zip

Now, from the catapult root directory, run:

dependency_manager/bin/update \\
  --config telemetry/telemetry/internal/binary_dependencies.json \\
  --dependency cv2 \\
  --path PATH/TO/cv2.zip \\
  --platform PLATFORM

where PATH/TO/cv2.zip is the file path of cv2.zip, and PLATFORM is the
current platform string, e.g. mac_x86_64 or win_AMD64.
EOF
