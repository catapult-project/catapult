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
from telemetry.core import browser_finder
from telemetry.core import command_line
from telemetry.core import util
from telemetry.page import page_runner
from telemetry.page import page_set
from telemetry.page import page_test
from telemetry.page import test_expectations
from telemetry.results import results_options
from telemetry.util import cloud_storage

Disabled = decorators.Disabled
Enabled = decorators.Enabled


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
    cls.PageTestClass().AddCommandLineArgs(parser)

    if hasattr(cls, 'AddTestCommandLineArgs'):
      group = optparse.OptionGroup(parser, '%s test options' % cls.Name())
      cls.AddTestCommandLineArgs(group)
      parser.add_option_group(group)

  @classmethod
  def SetArgumentDefaults(cls, parser):
    cls.PageTestClass().SetArgumentDefaults(parser)
    parser.set_defaults(**cls.options)

  @classmethod
  def ProcessCommandLineArgs(cls, parser, args):
    cls.PageTestClass().ProcessCommandLineArgs(parser, args)

  def CustomizeBrowserOptions(self, options):
    """Add browser options that are required by this benchmark."""

  def GetMetadata(self):
    return BenchmarkMetadata(self.Name())

  def Run(self, finder_options):
    """Run this test with the given options."""
    self.CustomizeBrowserOptions(finder_options.browser_options)

    pt = self.PageTestClass()()
    pt.__name__ = self.__class__.__name__

    if hasattr(self, '_disabled_strings'):
      pt._disabled_strings = self._disabled_strings
    if hasattr(self, '_enabled_strings'):
      pt._enabled_strings = self._enabled_strings

    ps = self.CreatePageSet(finder_options)
    expectations = self.CreateExpectations(ps)

    self._DownloadGeneratedProfileArchive(finder_options)

    benchmark_metadata = self.GetMetadata()
    results = results_options.CreateResults(benchmark_metadata, finder_options)
    try:
      page_runner.Run(pt, ps, expectations, finder_options, results)
    except page_test.TestNotSupportedOnPlatformFailure as failure:
      logging.warning(str(failure))

    results.PrintSummary()
    return len(results.failures)

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

  @classmethod
  def PageTestClass(cls):
    """Get the PageTest for this Benchmark.

    If the Benchmark has no PageTest, raises NotImplementedError.
    """
    if not hasattr(cls, 'test'):
      raise NotImplementedError('This test has no "test" attribute.')
    if not issubclass(cls.test, page_test.PageTest):
      raise TypeError('"%s" is not a PageTest.' % cls.test.__name__)
    return cls.test

  @classmethod
  def PageSetClass(cls):
    """Get the PageSet for this Benchmark.

    If the Benchmark has no PageSet, raises NotImplementedError.
    """
    if not hasattr(cls, 'page_set'):
      raise NotImplementedError('This test has no "page_set" attribute.')
    if not issubclass(cls.page_set, page_set.PageSet):
      raise TypeError('"%s" is not a PageSet.' % cls.page_set.__name__)
    return cls.page_set

  @classmethod
  def CreatePageSet(cls, options):  # pylint: disable=W0613
    """Get the page set this test will run on.

    By default, it will create a page set from the file at this test's
    page_set attribute. Override to generate a custom page set.
    """
    return cls.PageSetClass()()

  @classmethod
  def CreateExpectations(cls, ps):  # pylint: disable=W0613
    """Get the expectations this test will run with.

    By default, it will create an empty expectations set. Override to generate
    custom expectations.
    """
    return test_expectations.TestExpectations()


def AddCommandLineArgs(parser):
  page_runner.AddCommandLineArgs(parser)


def ProcessCommandLineArgs(parser, args):
  page_runner.ProcessCommandLineArgs(parser, args)
