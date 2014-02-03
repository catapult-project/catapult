#!/usr/bin/env python
# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import inspect
import unittest
import sys
import os

__all__ = []

class _TestLoader(unittest.TestLoader):
  def __init__(self, *args):
    super(_TestLoader, self).__init__(*args)
    self.discover_calls = []

  def loadTestsFromModule(self, module, use_load_tests=True):
    if module.__file__ != __file__:
      return super(_TestLoader, self).loadTestsFromModule(module, use_load_tests)

    suite = unittest.TestSuite()
    for discover_args in self.discover_calls:
      subsuite = self.discover(*discover_args)
      suite.addTest(subsuite)
    return suite

class TestRunner(object):
  def __init__(self):
    self._loader = _TestLoader()

  def AddModule(self, module, pattern="*unittest.py"):
    assert inspect.ismodule(module)
    module_file_basename = os.path.splitext(os.path.basename(module.__file__))[0]
    if module_file_basename != '__init__':
      raise NotImplementedError('Modules that are one file are not supported, only directories.')

    file_basename = os.path.basename(os.path.dirname(module.__file__))
    module_first_dir = module.__name__.split('.')[0]
    assert file_basename == module_first_dir, 'Module must be toplevel'

    start_dir = os.path.dirname(module.__file__)
    top_dir = os.path.normpath(os.path.join(os.path.dirname(module.__file__), '..'))
    self._loader.discover_calls.append((start_dir, pattern, top_dir))

  def Main(self, argv=None):
    if argv == None:
      argv = sys.argv
    return unittest.main(module=__name__, argv=argv, testLoader=self._loader)
