#!/bin/sh
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
BASEDIR=$(dirname $0)
SERVERPATH=$BASEDIR/stream_server/standalone.py
SERVERROOT=$BASEDIR/../
HANDLERSPATH=examples/stream_server/handlers
echo Navigate to http://localhost:8001/examples/stream_trace_viewer.html
python $SERVERPATH -d $SERVERROOT -w $HANDLERSPATH -p 8001
