# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core import util


util.AddDirToPythonPath(util.GetChromiumSrcDir(),
                        'third_party', 'py_trace_event', 'src')
from trace_event import *  # pylint: disable=import-error, wildcard-import
