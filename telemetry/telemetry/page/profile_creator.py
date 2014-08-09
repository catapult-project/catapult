# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.page import page_test

class ProfileCreator(page_test.PageTest):
  """Base class for an object that constructs a Chrome profile."""

  def __init__(self):
    super(ProfileCreator, self).__init__()
    self._page_set = None

  @property
  def page_set(self):
    return self._page_set

  def ValidateAndMeasurePage(self, _, tab, results):
    pass
