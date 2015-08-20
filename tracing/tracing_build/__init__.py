# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
import os
import sys


def _AddTracingProjectPath():
  tracing_path = os.path.normpath(
      os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
  if tracing_path not in sys.path:
    sys.path.insert(0, tracing_path)


_AddTracingProjectPath()
import tracing_project
tracing_project.UpdateSysPathIfNeeded()
