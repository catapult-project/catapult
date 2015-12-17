# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# All files in this directory should be moved to catapult/base/ after moving
# to the new repo.

import os
import sys

from catapult_base import util

def _AddDirToPythonPath(*path_parts):
  path = os.path.abspath(os.path.join(*path_parts))
  if os.path.isdir(path) and path not in sys.path:
    # Some callsite that use telemetry assumes that sys.path[0] is the directory
    # containing the script, so we add these extra paths to right after it.
    sys.path.insert(1, path)

_AddDirToPythonPath(os.path.join(util.GetCatapultDir(), 'third_party', 'mock'))

# TODO(nednguyen, aiolos): Copy these lib to catapult/third_party before
# actually moving catapult_base/ to catapult/
_AddDirToPythonPath(
    os.path.join(os.path.dirname(__file__), '..', 'third_party', 'mox3'))
_AddDirToPythonPath(
    os.path.join(os.path.dirname(__file__), '..', 'third_party', 'pyfakefs'))
