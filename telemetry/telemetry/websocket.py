# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import absolute_import
import os
import sys

def __init__():
  ws_path = os.path.join(os.path.dirname(__file__),
                         '../third_party/websocket-client')
  assert os.path.exists(os.path.join(ws_path, 'websocket.py'))
  sys.path.append(ws_path)

__init__()

from websocket import create_connection # pylint: disable=W0611
