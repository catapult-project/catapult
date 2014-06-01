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

  def RunSmokeTest(self, page_sets_dir):
    """Run smoke test on all page sets in page_sets_dir.

    Subclass of PageSetSmokeTest is supposed to call this in some test
    method to run smoke test.
    """
    # Instantiate all page sets and verify that all URLs have an associated
    # archive.
    page_sets = discover.GetAllPageSetFilenames(page_sets_dir)

    for page_set_path in page_sets:
      page_set = page_set_module.PageSet.FromFile(page_set_path)
      logging.info('Testing %s', page_set.file_path)
      self.CheckArchive(page_set)
      self.CheckCredentials(page_set)
