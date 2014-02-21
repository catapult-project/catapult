# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import shutil
import sys
import zipfile

from telemetry import decorators
from telemetry.core import browser_finder
from telemetry.core import repeat_options
from telemetry.core import util
from telemetry.page import page_runner
from telemetry.page import cloud_storage
from telemetry.page import page_set
from telemetry.page import page_test
from telemetry.page import test_expectations


Disabled = decorators.Disabled
Enabled = decorators.Enabled


class Test(object):
  """Base class for a Telemetry test or benchmark.

  A test packages a PageTest/PageMeasurement and a PageSet together.
  """
  options = {}

  @classmethod
  def GetName(cls):
    name = cls.__module__.split('.')[-1]
    if hasattr(cls, 'tag'):
      name += '.' + cls.tag
    if hasattr(cls, 'page_set'):
      name += '.' + os.path.basename(os.path.splitext(cls.page_set)[0])
    return name

  def Run(self, options):
    """Run this test with the given options."""
    assert hasattr(self, 'test'), 'This test has no "test" attribute.'
    assert issubclass(self.test, page_test.PageTest), (
            '"%s" is not a PageTest.' % self.test.__name__)

    for key, value in self.options.iteritems():
      setattr(options, key, value)

    if hasattr(self, '_disabled_strings'):
      self.test._disabled_strings = self._disabled_strings
    if hasattr(self, '_enabled_strings'):
      self.test._enabled_strings = self._enabled_strings

    options.repeat_options = self._CreateRepeatOptions(options)
    self.CustomizeBrowserOptions(options)

    test = self.test()
    test.__name__ = self.__class__.__name__
    ps = self.CreatePageSet(options)
    expectations = self.CreateExpectations(ps)

    # Ensure the test's default options are set if needed.
    parser = options.CreateParser()
    test.AddCommandLineOptions(parser)
    options.MergeDefaultValues(parser.get_default_values())

    self._DownloadGeneratedProfileArchive(options)

    results = page_runner.Run(test, ps, expectations, options)
    results.PrintSummary()
    return len(results.failures) + len(results.errors)

  def _CreateRepeatOptions(self, options):
    return repeat_options.RepeatOptions(
        getattr(options, 'page_repeat_secs', None),
        getattr(options, 'pageset_repeat_secs', None),
        getattr(options, 'page_repeat_iters', 1),
        getattr(options, 'pageset_repeat_iters', 1),
      )

  def _DownloadGeneratedProfileArchive(self, options):
    """Download and extract profile directory archive if one exists."""
    archive_name = getattr(self, 'generated_profile_archive', None)

    # If attribute not specified, nothing to do.
    if not archive_name:
      return

    # If profile dir specified on command line, nothing to do.
    if options.browser_options.profile_dir:
      logging.warning("Profile directory specified on command line: %s, this"
          "overrides the benchmark's default profile directory.",
          options.browser_options.profile_dir)
      return

    # Download profile directory from cloud storage.
    found_browser = browser_finder.FindBrowser(options)
    test_data_dir = os.path.join(util.GetChromiumSrcDir(), 'tools', 'perf',
        'generated_profiles',
        found_browser.target_os)
    generated_profile_archive_path = os.path.normpath(
        os.path.join(test_data_dir, archive_name))

    try:
      cloud_storage.GetIfChanged(generated_profile_archive_path,
          cloud_storage.PUBLIC_BUCKET)
    except (cloud_storage.CredentialsError,
            cloud_storage.PermissionError) as e:
      if os.path.exists(generated_profile_archive_path):
        # If the profile directory archive exists, assume the user has their
        # own local copy simply warn.
        logging.warning('Could not download Profile archive: %s',
            generated_profile_archive_path)
      else:
        # If the archive profile directory doesn't exist, this is fatal.
        logging.error('Can not run without required profile archive: %s. '
                      'If you believe you have credentials, follow the '
                      'instructions below.',
                      generated_profile_archive_path)
        logging.error(e)
        sys.exit(1)

    # Unzip profile directory.
    extracted_profile_dir_path = (
        os.path.splitext(generated_profile_archive_path)[0])
    if not os.path.isfile(generated_profile_archive_path):
      raise Exception("Profile directory archive not downloaded: ",
          generated_profile_archive_path)
    with zipfile.ZipFile(generated_profile_archive_path) as f:
      try:
        f.extractall(os.path.dirname(generated_profile_archive_path))
      except e:
        # Cleanup any leftovers from unzipping.
        if os.path.exists(extracted_profile_dir_path):
          shutil.rmtree(extracted_profile_dir_path)
        logging.error("Error extracting profile directory zip file: %s", e)
        sys.exit(1)

    # Run with freshly extracted profile directory.
    logging.info("Using profile archive directory: %s",
        extracted_profile_dir_path)
    options.browser_options.profile_dir = extracted_profile_dir_path

  def CreatePageSet(self, options):  # pylint: disable=W0613
    """Get the page set this test will run on.

    By default, it will create a page set from the file at this test's
    page_set attribute. Override to generate a custom page set.
    """
    if not hasattr(self, 'page_set'):
      raise NotImplementedError('This test has no "page_set" attribute.')
    return page_set.PageSet.FromFile(
        os.path.join(util.GetBaseDir(), self.page_set))

  def CreateExpectations(self, ps):  # pylint: disable=W0613
    """Get the expectations this test will run with.

    By default, it will create an empty expectations set. Override to generate
    custom expectations.
    """
    if hasattr(self, 'expectations'):
      return self.expectations
    else:
      return test_expectations.TestExpectations()

  @staticmethod
  def AddCommandLineOptions(parser):
    page_runner.AddCommandLineOptions(parser)

  @staticmethod
  def AddTestCommandLineOptions(parser):
    """Override to accept custom command line options."""
    pass

  def CustomizeBrowserOptions(self, options):
    """Add browser options that are required by this benchmark."""
    pass
