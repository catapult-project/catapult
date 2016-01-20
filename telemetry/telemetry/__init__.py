# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A library for cross-platform browser tests."""
import os
import sys

from telemetry.core import util


# Ensure Python >= 2.7.
if sys.version_info < (2, 7):
  print >> sys.stderr, 'Need Python 2.7 or greater.'
  sys.exit(-1)


def _JoinPath(*path_parts):
  return os.path.abspath(os.path.join(*path_parts))

def _AddDirToPythonPath(*path_parts):
  path = _JoinPath(*path_parts)
  if os.path.isdir(path) and path not in sys.path:
    # Some call sites that use Telemetry assume that sys.path[0] is the
    # directory containing the script, so we add these extra paths to right
    # after sys.path[0].
    sys.path.insert(1, path)

# Add Catapult dependencies to our path.
_AddDirToPythonPath(util.GetCatapultDir(), 'catapult_base')
_AddDirToPythonPath(util.GetCatapultDir(), 'dependency_manager')
_AddDirToPythonPath(util.GetCatapultDir(), 'tracing')


# Add Telemetry third party dependencies into our path.
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

# Install Telemtry global hooks.
from telemetry.internal.util import global_hooks
global_hooks.InstallHooks()
