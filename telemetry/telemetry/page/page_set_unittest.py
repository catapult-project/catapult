# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import tempfile
import unittest

from telemetry.core import util
from telemetry.page import page_set


class TestPageSet(unittest.TestCase):
  def testServingDirs(self):
    directory_path = tempfile.mkdtemp()
    try:
      ps = page_set.PageSet.FromDict({
        'serving_dirs': ['a/b'],
        'pages': [
          {'url': 'file://c/test.html'},
          {'url': 'file://c/test.js'},
          {'url': 'file://d/e/../test.html'},
          ]
        }, directory_path)
    finally:
      os.rmdir(directory_path)

    real_directory_path = os.path.realpath(directory_path)
    expected_serving_dirs = set([os.path.join(real_directory_path, 'a', 'b')])
    self.assertEquals(ps.serving_dirs, expected_serving_dirs)
    self.assertEquals(ps[0].serving_dir, os.path.join(real_directory_path, 'c'))
    self.assertEquals(ps[2].serving_dir, os.path.join(real_directory_path, 'd'))

  def testRenamingCompoundActions(self):
    ps = page_set.PageSet.FromDict({
      'serving_dirs': ['a/b'],
      'smoothness' : { 'action' : 'scroll' },
      'pages': [
        {'url': 'http://www.foo.com',
         'stress_memory': {'action': 'javasciprt'}
        },
        {'url': 'http://www.bar.com',
         'navigate_steps': {'action': 'navigate2'},
         'repaint' : {'action': 'scroll'}
        },
      ]}, 'file://foo.js')

    self.assertTrue(hasattr(ps.pages[0], 'RunNavigateSteps'))
    self.assertEquals(ps.pages[0].RunSmoothness, {'action': 'scroll'})
    self.assertEquals(ps.pages[0].RunStressMemory, {'action': 'javasciprt'})

    self.assertEquals(ps.pages[1].RunSmoothness, {'action': 'scroll'})
    self.assertEquals(ps.pages[1].RunNavigateSteps, {'action': 'navigate2'})
    self.assertEquals(ps.pages[1].RunRepaint, {'action': 'scroll'})

  def testRunNavigateStepsInheritance(self):
    ps = page_set.PageSet.FromDict({
      'serving_dirs': ['a/b'],
      'navigate_steps' : { 'action' : 'navigate1' },
      'pages': [
        {'url': 'http://www.foo.com',
        },
        {'url': 'http://www.bar.com',
         'navigate_steps': {'action': 'navigate2'},
        },
      ]}, 'file://foo.js')

    self.assertEquals(ps.pages[0].RunNavigateSteps, {'action': 'navigate1'})
    self.assertEquals(ps.pages[1].RunNavigateSteps, {'action': 'navigate2'})


  def testSuccesfulPythonPageSetLoading(self):
    test_pps_dir = os.path.join(util.GetUnittestDataDir(), 'test_page_set.py')
    pps = page_set.PageSet.FromFile(test_pps_dir)
    self.assertEqual('TestPageSet', pps.__class__.__name__)
    self.assertEqual('A pageset for testing purpose', pps.description)
    self.assertEqual('data/test.json', pps.archive_data_file)
    self.assertEqual('data/credential', pps.credentials_path)
    self.assertEqual('desktop', pps.user_agent_type)
    self.assertEqual(test_pps_dir, pps.file_path)
    self.assertEqual(3, len(pps.pages))
    google_page = pps.pages[0]
    self.assertEqual('https://www.google.com', google_page.url)
    self.assertIs(pps, google_page.page_set)
    self.assertTrue(5, google_page.RunGetActionRunner(action_runner=5))

  def testMultiplePythonPageSetsLoading(self):
    test_pps_1_dir = os.path.join(util.GetUnittestDataDir(),
                                'test_simple_one_page_set.py')
    test_pps_2_dir = os.path.join(util.GetUnittestDataDir(),
                                'test_simple_two_page_set.py')
    pps1 = page_set.PageSet.FromFile(test_pps_1_dir)
    pps2 = page_set.PageSet.FromFile(test_pps_2_dir)

    self.assertEqual('TestSimpleOnePageSet', pps1.__class__.__name__)
    self.assertEqual('TestSimpleTwoPageSet', pps2.__class__.__name__)

  def testPageFilePath(self):
    test_pps_dir = os.path.join(util.GetUnittestDataDir(), 'test_page_set.py')
    pps = page_set.PageSet.FromFile(test_pps_dir)
    internal_page = pps.pages[1]
    external_page = pps.pages[2]
    self.assertEqual(
      os.path.normpath(os.path.join(
        util.GetUnittestDataDir(), 'bar.html')), internal_page.file_path)
    self.assertEqual(
      os.path.normpath(os.path.join(
        util.GetUnittestDataDir(), 'pages/foo.html')), external_page.file_path)
