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

  def testDiscoverClassesWithDefaults(self):
    classes = discover.DiscoverClasses(
        self._start_dir, self._base_dir, self._base_class)

    actual_classes = list(cls.__name__ for cls in classes)
    expected_classes = [
        'DummyException', 'DummyExceptionImpl1', 'DummyExceptionImpl2',
        'DummyExceptionWithParameterImpl1', 'DummyExceptionWithParameterImpl2'
    ]
    self.assertItemsEqual(actual_classes, expected_classes)


  def testDiscoverClassesOneClassPerModule(self):
    classes = discover.DiscoverClasses(
        self._start_dir, self._base_dir, self._base_class,
        one_class_per_module=True)

    actual_classes = list(cls.__name__ for cls in classes)
    expected_classes = ['DummyExceptionImpl1', 'DummyException',
                        'DummyExceptionWithParameterImpl2']
    self.assertItemsEqual(actual_classes, expected_classes)

  def testDiscoverDirectlyConstructableClasses(self):
    classes = discover.DiscoverClasses(
        self._start_dir, self._base_dir, self._base_class,
        directly_constructable=True)

    actual_classes = list(cls.__name__ for cls in classes)
    expected_classes = [
        'DummyException', 'DummyExceptionImpl1', 'DummyExceptionImpl2'
    ]
    self.assertItemsEqual(actual_classes, expected_classes)

  def testDiscoverOneDirectlyConstructableClassPerModule(self):
    classes = discover.DiscoverClasses(
        self._start_dir, self._base_dir, self._base_class,
        directly_constructable=True, one_class_per_module=True)

    actual_classes = list(cls.__name__ for cls in classes)
    expected_classes = ['DummyException', 'DummyExceptionImpl1']
    self.assertItemsEqual(actual_classes, expected_classes)

  def testDiscoverClassesWithPattern(self):
    classes = discover.DiscoverClasses(
        self._start_dir, self._base_dir, self._base_class,
        pattern='another*')

    actual_classes = list(cls.__name__ for cls in classes)
    expected_classes = ['DummyExceptionImpl1', 'DummyExceptionImpl2',
                        'DummyExceptionWithParameterImpl1']
    self.assertItemsEqual(actual_classes, expected_classes)

  def testDiscoverOneClassPerModuleWithPattern(self):
    classes = discover.DiscoverClasses(
        self._start_dir, self._base_dir, self._base_class,
        pattern='another*', one_class_per_module=True)

    actual_classes = list(cls.__name__ for cls in classes)
    expected_classes = ['DummyExceptionImpl1']
    self.assertItemsEqual(actual_classes, expected_classes)

  def testDiscoverDirectlyConstructableClassesWithPattern(self):
    classes = discover.DiscoverClasses(
        self._start_dir, self._base_dir, self._base_class,
        pattern='another*', directly_constructable=True)

    actual_classes = list(cls.__name__ for cls in classes)
    expected_classes = ['DummyExceptionImpl1', 'DummyExceptionImpl2']
    self.assertItemsEqual(actual_classes, expected_classes)

  def testDiscoverOneDirectlyConstructableClassPerModuleWithPattern(self):
    classes = discover.DiscoverClasses(
        self._start_dir, self._base_dir, self._base_class,
        pattern='another*', directly_constructable=True,
        one_class_per_module=True)

    actual_classes = list(cls.__name__ for cls in classes)
    expected_classes = ['DummyExceptionImpl1']
    self.assertItemsEqual(actual_classes, expected_classes)
