# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import absolute_import

from telemetry.core import util

util.AddDirToPythonPath(util.GetChromiumSrcDir(), 'tools')
from crx_id import crx_id  # pylint: disable=F0401


GetCRXAppID = crx_id.GetCRXAppID
HasPublicKey = crx_id.HasPublicKey
