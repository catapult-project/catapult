# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys

sys.path.append(os.path.normpath(os.path.join(
    os.path.dirname(__file__), '..', '..', 'common', 'py_utils')))

from py_utils.cloud_storage import *
