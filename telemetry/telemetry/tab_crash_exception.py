# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
class TabCrashException(Exception):
  """Represnets a crash of the current tab, but not the overall browser.

  In this state, the tab is gone, but the underlying browser is still alive."""
  pass

