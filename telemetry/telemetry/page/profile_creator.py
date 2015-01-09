# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.page import page_test

class ProfileCreator(object):
  """Abstract base class for an object that constructs a Chrome profile."""

  def Run(self, options):
    """Creates the profile.

    |options| is an instance of BrowserFinderOptions. When subclass
    implementations of this method inevitably attempt to find and launch a
    browser, they should pass |options| to the relevant methods.

    Several properties of |options| might require direct manipulation by
    subclasses. These are:
      |options.output_profile_path|: The path at which the profile should be
      created.
      |options.browser_options.profile_dir|: If this property is None, then a
      new profile is created. Otherwise, the existing profile is appended on
      to.
    """
    raise NotImplementedError()
