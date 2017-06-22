# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Shim for discover; will be removed once #3612 is fixed."""

from py_utils import discover

DiscoverClasses = discover.DiscoverClasses
DiscoverClassesInModule = discover.DiscoverClassesInModule
