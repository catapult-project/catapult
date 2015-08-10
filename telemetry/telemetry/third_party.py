# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from telemetry.core import util

# To expose modules from third_party through telemetry.third_party, follow the
# example below.

util.AddDirToPythonPath(util.GetTelemetryDir(), 'third_party', 'mock')
import mock # pylint: disable=unused-import
