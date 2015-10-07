# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A library for cross-platform browser tests."""
import os
import sys

# Ensure Python >= 2.7.
if sys.version_info < (2, 7):
  print >> sys.stderr, 'Need Python 2.7 or greater.'
  sys.exit(-1)

from telemetry.internal.util import global_hooks
global_hooks.InstallHooks()

# Add depdendencies into our path.
from telemetry.core import util

def _AddDirToPythonPath(*path_parts):
  path = os.path.abspath(os.path.join(*path_parts))
  if os.path.isdir(path) and path not in sys.path:
    # Some callsite that use telemetry assumes that sys.path[0] is the directory
    # containing the script, so we add these extra paths to right after it.
    sys.path.insert(1, path)


_AddDirToPythonPath(util.GetTelemetryThirdPartyDir(), 'altgraph')
_AddDirToPythonPath(util.GetTelemetryThirdPartyDir(), 'mock')
_AddDirToPythonPath(util.GetTelemetryThirdPartyDir(), 'modulegraph')
_AddDirToPythonPath(util.GetTelemetryThirdPartyDir(), 'mox3')
_AddDirToPythonPath(util.GetTelemetryThirdPartyDir(), 'pexpect')
_AddDirToPythonPath(util.GetTelemetryThirdPartyDir(), 'png')
_AddDirToPythonPath(util.GetTelemetryThirdPartyDir(), 'pyfakefs')
_AddDirToPythonPath(util.GetTelemetryThirdPartyDir(), 'pyserial')
_AddDirToPythonPath(util.GetTelemetryThirdPartyDir(), 'typ')
_AddDirToPythonPath(util.GetTelemetryThirdPartyDir(), 'webpagereplay')
_AddDirToPythonPath(util.GetTelemetryThirdPartyDir(), 'websocket-client')

_AddDirToPythonPath(os.path.dirname(__file__), os.path.pardir, os.path.pardir,
                    os.path.pardir, 'build', 'android')

_AddDirToPythonPath(os.path.dirname(__file__), os.path.pardir, os.path.pardir,
                    os.path.pardir, 'third_party', 'catapult', 'tracing')
