#!/bin/bash
set -x

LICENSE_HEADER="<!--
Copyright 2017 The Chromium Authors. All rights reserved.
Use of this source code is governed by a BSD-style license that can be
found in the LICENSE file.
-->
"

git checkout master
REV=`git rev-parse HEAD`
tracing/bin/vulcanize_trace_viewer --config=full
cp tracing/bin/trace_viewer_full.html /tmp/
git checkout vulcanized_traceviewer
echo "${LICENSE_HEADER}" > ./trace_viewer_full.html
cat /tmp/trace_viewer_full.html >> ./trace_viewer_full.html
git add trace_viewer_full.html
git commit -m "Update trace_viewer.html to $REV"
