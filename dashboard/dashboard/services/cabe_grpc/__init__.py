# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This is necessary because python and/or protoc is garbage:
# https://github.com/protocolbuffers/protobuf/issues/1491
from __future__ import absolute_import
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))
