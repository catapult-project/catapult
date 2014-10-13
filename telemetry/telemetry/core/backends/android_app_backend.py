# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core.backends import app_backend


class AndroidAppBackend(app_backend.AppBackend):
  def __init__(self):
    super(AndroidAppBackend, self).__init__()
