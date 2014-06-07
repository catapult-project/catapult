# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import unittest

from telemetry.core import browser_credentials
from telemetry.core import discover
from telemetry.page import page_set as page_set_module
from telemetry.page import page_set_archive_info


class PageSetSmokeTest(unittest.TestCase):

  def CheckArchive(self, page_set):
    """Verify that all URLs of pages in page_set have an associated archive. """
    # TODO: Eventually these should be fatal.
    if not page_set.archive_data_file:
      logging.warning('Skipping %s: no archive data file', page_set.file_path)
      return

    logging.info('Testing %s', page_set.file_path)

    archive_data_file_path = os.path.join(page_set.base_dir,
                                          page_set.archive_data_file)
    self.assertTrue(os.path.exists(archive_data_file_path),
                    msg='Archive data file not found for %s' %
                    page_set.file_path)

    wpr_archive_info = page_set_archive_info.PageSetArchiveInfo.FromFile(
        archive_data_file_path, ignore_archive=True)
    for page in page_set.pages:
      if not page.url.startswith('http'):
        continue
      self.assertTrue(wpr_archive_info.WprFilePathForPage(page),
                      msg='No archive found for %s in %s' % (
                          page.url, page_set.archive_data_file))

  def CheckCredentials(self, page_set):
    """Verify that all pages in page_set use proper credentials"""
    credentials = browser_credentials.BrowserCredentials()
    if page_set.credentials_path:
      credentials.credentials_path = (
          os.path.join(page_set.base_dir, page_set.credentials_path))
    for page in page_set.pages:
      fail_message = ('page %s of %s has invalid credentials %s' %
                      (page.url, page_set.file_path, page.credentials))
      if page.credentials:
        try:
          self.assertTrue(credentials.CanLogin(page.credentials), fail_message)
        except browser_credentials.CredentialsError:
          self.fail(fail_message)

  def CheckTypes(self, page_set):
    """Verify that page_set and its page's base attributes have the right types.
    """
    self.CheckTypesOfPageSetBasicAttributes(page_set)
    for page in page_set.pages:
      self.CheckTypesOfPageBasicAttributes(page)

  def CheckTypesOfPageSetBasicAttributes(self, page_set):
    if page_set.file_path is not None:
      self.assertTrue(
          isinstance(page_set.file_path, str),
          msg='page_set %\'s file_path must have type string')

    self.assertTrue(
        isinstance(page_set.archive_data_file, str),
        msg='page_set\'s archive_data_file path must have type string')

    if page_set.user_agent_type is not None:
      self.assertTrue(
          isinstance(page_set.user_agent_type, str),
          msg='page_set\'s user_agent_type must have type string')

    self.assertTrue(
        isinstance(page_set.make_javascript_deterministic, bool),
        msg='page_set\'s make_javascript_deterministic must have type bool')

    self.assertTrue(
        isinstance(page_set.startup_url, str),
        msg='page_set\'s startup_url must have type string')

  def CheckTypesOfPageBasicAttributes(self, page):
    self.assertTrue(
       isinstance(page.url, str),
       msg='page %s \'s url must have type string' % page.display_name)
    self.assertTrue(
       isinstance(page.page_set, page_set_module.PageSet),
       msg='page %s \'s page_set must be an instance of '
       'telemetry.page.page_set.PageSet' % page.display_name)
    self.assertTrue(
       isinstance(page.name, str),
       msg='page %s \'s name field must have type string' % page.display_name)

  def RunSmokeTest(self, page_sets_dir, top_level_dir):
    """Run smoke test on all page sets in page_sets_dir.

    Subclass of PageSetSmokeTest is supposed to call this in some test
    method to run smoke test.
    """
    page_sets = discover.DiscoverClasses(page_sets_dir, top_level_dir,
                                         page_set_module.PageSet).values()
    for page_set_class in page_sets:
      page_set = page_set_class()
      logging.info('Testing %s', page_set.file_path)
      self.CheckArchive(page_set)
      self.CheckCredentials(page_set)
      self.CheckTypes(page_set)
