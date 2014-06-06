# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core import util

# Bring in tvcm module for basic JS components capabilities.
util.AddDirToPythonPath(
    util.GetChromiumSrcDir(),
    'third_party', 'trace-viewer', 'third_party', 'tvcm')

# Bring in trace_viewer module for the UI features that are part of the trace
# viewer.
util.AddDirToPythonPath(
    util.GetChromiumSrcDir(),
    'third_party', 'trace-viewer')
