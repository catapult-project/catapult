# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
class BrowserGoneException(Exception):
  """Represents a crash of the entire browser.

  In this state, all bets are pretty much off."""
  pass

class BrowserConnectionGoneException(BrowserGoneException):
  pass
