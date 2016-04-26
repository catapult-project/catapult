# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.page import legacy_page_test

# TODO(nednguyen): Remove this shim after all the call sites are updated to
# reference telemetry.legacy_page_test (crbug.com/606643)
PageTest = legacy_page_test.LegacyPageTest
