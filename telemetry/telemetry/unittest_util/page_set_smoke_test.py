# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import unittest

from telemetry.core import browser_credentials
from telemetry.core import discover
from telemetry.page import page_set as page_set_module
from telemetry.util import classes
from telemetry.wpr import archive_info


class PageSetSmokeTest(unittest.TestCase):

  def setUp(self):
    # Make sure the added failure message is appended to the default failure
    # message.
    self.longMessage = True

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

    wpr_archive_info = archive_info.WprArchiveInfo.FromFile(
        archive_data_file_path, page_set.bucket)
    for page in page_set.pages:
      if not page.url.startswith('http'):
        continue
      self.assertTrue(wpr_archive_info.WprFilePathForUserStory(page),
                      msg='No archive found for %s in %s' % (
                          page.url, page_set.archive_data_file))

  def CheckCredentials(self, page_set):
    """Verify that all pages in page_set use proper credentials"""
    for page in page_set.pages:
      credentials = browser_credentials.BrowserCredentials()
      if page.credentials_path:
        credentials.credentials_path = (
            os.path.join(page.base_dir, page.credentials_path))
      fail_message = ('page %s of %s has invalid credentials %s' %
                      (page.url, page_set.file_path, page.credentials))
      if page.credentials:
        try:
          self.assertTrue(credentials.CanLogin(page.credentials), fail_message)
        except browser_credentials.CredentialsError:
          self.fail(fail_message)

  def CheckAttributes(self, page_set):
    """Verify that page_set and its page's base attributes have the right types.
    """
    self.CheckAttributesOfPageSetBasicAttributes(page_set)
    for page in page_set.pages:
      self.CheckAttributesOfPageBasicAttributes(page)

  def CheckAttributesOfPageSetBasicAttributes(self, page_set):
    if page_set.base_dir is not None:
      self.assertTrue(
          isinstance(page_set.base_dir, str),
          msg='page_set %\'s base_dir must have type string')

    self.assertTrue(
        isinstance(page_set.archive_data_file, str),
        msg='page_set\'s archive_data_file path must have type string')

    if page_set.user_agent_type is not None:
      self.assertTrue(
          isinstance(page_set.user_agent_type, str),
          msg='page_set\'s user_agent_type must have type string')

  def CheckAttributesOfPageBasicAttributes(self, page):
    self.assertTrue(not hasattr(page, 'disabled'))
    self.assertTrue(
       # We use basestring instead of str because page's url can be string of
       # unicode.
       isinstance(page.url, basestring),
       msg='page %s \'s url must have type string' % page.display_name)
    self.assertTrue(
       isinstance(page.page_set, page_set_module.PageSet),
       msg='page %s \'s page_set must be an instance of '
       'telemetry.page.page_set.PageSet' % page.display_name)
    self.assertTrue(
       isinstance(page.name, str),
       msg='page %s \'s name field must have type string' % page.display_name)
    self.assertTrue(
       isinstance(page.labels, set),
       msg='page %s \'s labels field must have type set' % page.display_name)
    self.assertTrue(
        isinstance(page.startup_url, str),
        msg=('page %s \'s startup_url field must have type string'
            % page.display_name))
    self.assertIsInstance(
        page.make_javascript_deterministic, bool,
        msg='page %s \'s make_javascript_deterministic must have type bool'
            % page.display_name)
    for l in page.labels:
      self.assertTrue(
         isinstance(l, str),
         msg='label %s in page %s \'s labels must have type string'
         % (str(l), page.display_name))

  def CheckSharedStates(self, page_set):
    if not page_set.allow_mixed_story_states:
      shared_user_story_state_class = (
          page_set.user_stories[0].shared_user_story_state_class)
      for p in page_set:
        self.assertIs(
            shared_user_story_state_class,
            p.shared_user_story_state_class,
            msg='page %s\'s shared_user_story_state_class field is different '
            'from other pages\'s shared_user_story_state_class whereas '
            'page set %s disallow having mixed states' %
            (p, page_set))

  def RunSmokeTest(self, page_sets_dir, top_level_dir):
    """Run smoke test on all page sets in page_sets_dir.

    Subclass of PageSetSmokeTest is supposed to call this in some test
    method to run smoke test.
    """
    page_sets = discover.DiscoverClasses(page_sets_dir, top_level_dir,
                                         page_set_module.PageSet).values()
    for page_set_class in page_sets:
      if not classes.IsDirectlyConstructable(page_set_class):
        # We can't test page sets that aren't directly constructable since we
        # don't know what arguments to put for the constructor.
        continue
      page_set = page_set_class()
      logging.info('Testing %s', page_set.file_path)
      self.CheckArchive(page_set)
      self.CheckCredentials(page_set)
      self.CheckAttributes(page_set)
      self.CheckSharedStates(page_set)
