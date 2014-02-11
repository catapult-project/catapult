# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry import decorators


class Foo(object):
  pass


def CreateFooUncached(_):
  return Foo()


@decorators.Cache
def CreateFooCached(_):
  return Foo()


class DecoratorsUnitTest(unittest.TestCase):

  def testCacheDecorator(self):
    self.assertNotEquals(CreateFooUncached(1), CreateFooUncached(2))
    self.assertNotEquals(CreateFooCached(1), CreateFooCached(2))

    self.assertNotEquals(CreateFooUncached(1), CreateFooUncached(1))
    self.assertEquals(CreateFooCached(1), CreateFooCached(1))
