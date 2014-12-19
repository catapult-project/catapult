# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import optparse
import os
import shutil
import sys
import zipfile

from telemetry import decorators
from telemetry import page
from telemetry.core import browser_finder
from telemetry.core import command_line
from telemetry.core import util
from telemetry.user_story import user_story_runner
from telemetry.page import page_set
from telemetry.page import page_test
from telemetry.page import test_expectations
from telemetry.results import results_options
from telemetry.util import cloud_storage
from telemetry.util import exception_formatter

Disabled = decorators.Disabled
Enabled = decorators.Enabled


class InvalidOptionsError(Exception):
  """Raised for invalid benchmark options."""
  pass


class BenchmarkMetadata(object):
  def __init__(self, name):
    self._name = name

  @property
  def name(self):
    return self._name

class Benchmark(command_line.Command):
  """Base class for a Telemetry benchmark.

  A test packages a PageTest and a PageSet together.
  """
  options = {}

  def __init__(self, max_failures=None):
    """Creates a new Benchmark.

    Args:
      max_failures: The number of user story run's failures before bailing
          from executing subsequent page runs. If None, we never bail.
    """
    self._max_failures = max_failures

  @classmethod
  def Name(cls):
    name = cls.__module__.split('.')[-1]
    if hasattr(cls, 'tag'):
      name += '.' + cls.tag
    if hasattr(cls, 'page_set'):
      name += '.' + cls.page_set.Name()
    return name

  @classmethod
  def AddCommandLineArgs(cls, parser):
    if hasattr(cls, 'AddBenchmarkCommandLineArgs'):
      group = optparse.OptionGroup(parser, '%s test options' % cls.Name())
      cls.AddBenchmarkCommandLineArgs(group)
      parser.add_option_group(group)

  @classmethod
  def SetArgumentDefaults(cls, parser):
    default_values = parser.get_default_values()
    invalid_options = [
        o for o in cls.options if not hasattr(default_values, o)]
    if invalid_options:
      raise InvalidOptionsError('Invalid benchmark options: %s',
                                ', '.join(invalid_options))
    parser.set_defaults(**cls.options)

  @classmethod
  def ProcessCommandLineArgs(cls, parser, args):
    pass

  def CustomizeBrowserOptions(self, options):
    """Add browser options that are required by this benchmark."""

  def GetMetadata(self):
    return BenchmarkMetadata(self.Name())

  def Run(self, finder_options):
    """Run this test with the given options.

    Returns:
      The number of failure values (up to 254) or 255 if there is an uncaught
      exception.
    """
    self.CustomizeBrowserOptions(finder_options.browser_options)

    pt = self.CreatePageTest(finder_options)
    pt.__name__ = self.__class__.__name__

    if hasattr(self, '_disabled_strings'):
      # pylint: disable=protected-access
      pt._disabled_strings = self._disabled_strings
    if hasattr(self, '_enabled_strings'):
      # pylint: disable=protected-access
      pt._enabled_strings = self._enabled_strings

    expectations = self.CreateExpectations()
    us = self.CreateUserStorySet(finder_options)
    if isinstance(pt, page_test.PageTest):
      if any(not isinstance(p, page.Page) for p in us.user_stories):
        raise Exception(
            'PageTest must be used with UserStorySet containing only '
            'telemetry.page.Page user stories.')

    self._DownloadGeneratedProfileArchive(finder_options)

    benchmark_metadata = self.GetMetadata()
    results = results_options.CreateResults(benchmark_metadata, finder_options)
    try:
      user_story_runner.Run(pt, us, expectations, finder_options, results,
                            max_failures=self._max_failures)
      return_code = min(254, len(results.failures))
    except Exception:
      exception_formatter.PrintFormattedException()
      return_code = 255

    bucket = cloud_storage.BUCKET_ALIASES[finder_options.upload_bucket]
    if finder_options.upload_results:
      results.UploadTraceFilesToCloud(bucket)
      results.UploadProfilingFilesToCloud(bucket)

    results.PrintSummary()
    return return_code

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
        logging.error(str(e))
        sys.exit(-1)

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
        sys.exit(-1)

    # Run with freshly extracted profile directory.
    logging.info("Using profile archive directory: %s",
        extracted_profile_dir_path)
    options.browser_options.profile_dir = extracted_profile_dir_path

  def CreatePageTest(self, options):  # pylint: disable=W0613
    """Get the PageTest for this Benchmark.

    By default, it will create a page test from the test's test attribute.
    Override to generate a custom page test.
    """
    if not hasattr(self, 'test'):
      raise NotImplementedError('This test has no "test" attribute.')
    if not issubclass(self.test, page_test.PageTest):
      raise TypeError('"%s" is not a PageTest.' % self.test.__name__)
    return self.test()

  def CreatePageSet(self, options):  # pylint: disable=W0613
    """Get the page set this test will run on.

    By default, it will create a page set from the this test's page_set
    attribute. Override to generate a custom page set.
    """
    if not hasattr(self, 'page_set'):
      raise NotImplementedError('This test has no "page_set" attribute.')
    if not issubclass(self.page_set, page_set.PageSet):
      raise TypeError('"%s" is not a PageSet.' % self.page_set.__name__)
    return self.page_set()

  def CreateUserStorySet(self, options):
    return self.CreatePageSet(options)

  @classmethod
  def CreateExpectations(cls):
    """Get the expectations this test will run with.

    By default, it will create an empty expectations set. Override to generate
    custom expectations.
    """
    return test_expectations.TestExpectations()


def AddCommandLineArgs(parser):
  user_story_runner.AddCommandLineArgs(parser)


def ProcessCommandLineArgs(parser, args):
  user_story_runner.ProcessCommandLineArgs(parser, args)
