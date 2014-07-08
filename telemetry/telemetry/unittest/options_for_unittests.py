# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module provides the global variable options_for_unittests.

This is set to a BrowserOptions object by the test harness, or None
if unit tests are not running.

This allows multiple unit tests to use a specific
browser, in face of multiple options."""


_options = None


def Set(options):
  global _options

  _options = options


def GetCopy():
  if not _options:
    return None

  return _options.Copy()


def AreSet():
  if _options:
    return True
  return False
