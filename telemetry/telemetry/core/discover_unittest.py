# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import unittest

from telemetry.core import discover
from telemetry.core import util


class DiscoverTest(unittest.TestCase):
  def setUp(self):
    self._base_dir = util.GetUnittestDataDir()
    self._start_dir = os.path.join(self._base_dir, 'discoverable_classes')
    self._base_class = Exception

  def testDiscoverClassesBasic(self):
    classes = discover.DiscoverClasses(
        self._start_dir, self._base_dir, self._base_class)

    actual_classes = dict(
        (name, cls.__name__) for name, cls in classes.iteritems())
    expected_classes = {
        'discover_dummyclass': 'DummyException',
        'another_discover_dummyclass': 'DummyExceptionImpl2',
    }
    self.assertEqual(actual_classes, expected_classes)

  def testDiscoverClassesWithPattern(self):
    classes = discover.DiscoverClasses(
        self._start_dir, self._base_dir, self._base_class,
        pattern='another*')

    actual_classes = dict(
        (name, cls.__name__) for name, cls in classes.iteritems())
    expected_classes = {
        'another_discover_dummyclass': 'DummyExceptionImpl2',
    }
    self.assertEqual(actual_classes, expected_classes)

  def testDiscoverClassesByClassName(self):
    classes = discover.DiscoverClasses(
        self._start_dir, self._base_dir, self._base_class,
        index_by_class_name=True)

    actual_classes = dict(
        (name, cls.__name__) for name, cls in classes.iteritems())
    expected_classes = {
        'dummy_exception': 'DummyException',
        'dummy_exception_impl1': 'DummyExceptionImpl1',
        'dummy_exception_impl2': 'DummyExceptionImpl2',
    }
    self.assertEqual(actual_classes, expected_classes)
