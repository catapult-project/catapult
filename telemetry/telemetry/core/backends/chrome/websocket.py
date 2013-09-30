# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import absolute_import

from telemetry.core import util

util.AddDirToPythonPath(
    util.GetTelemetryDir(), 'third_party', 'websocket-client')
from websocket import create_connection  # pylint: disable=W0611
from websocket import WebSocketException  # pylint: disable=W0611
from websocket import WebSocketTimeoutException  # pylint: disable=W0611
