# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry import decorators
import mock


class FakePlatform(object):
  def GetOSName(self):
    return 'os_name'

  def GetOSVersionName(self):
    return 'os_version_name'


class FakePossibleBrowser(object):
  def __init__(self):
    self.browser_type = 'browser_type'
    self.platform = FakePlatform()
    self.supports_tab_control = False


class FakeTest(object):
  def SetEnabledStrings(self, enabled_strings):
    # pylint: disable=W0201
    self._enabled_strings = enabled_strings

  def SetDisabledStrings(self, disabled_strings):
    # pylint: disable=W0201
    self._disabled_strings = disabled_strings


class TestDisableDecorators(unittest.TestCase):

  def testDisabledStringOnFunction(self):
    @decorators.Disabled('bar')
    def Sum():
      return 1 + 1
    self.assertEquals({'bar'}, Sum._disabled_strings)

    @decorators.Disabled('bar')
    @decorators.Disabled('baz')
    @decorators.Disabled('bart', 'baz')
    def Product():
      return 1 * 1
    self.assertEquals({'bar', 'bart', 'baz'}, Product._disabled_strings)

  def testDisabledStringOnClass(self):
    @decorators.Disabled('windshield')
    class Ford(object):
      pass
    self.assertEquals({'windshield'}, Ford._disabled_strings)

    @decorators.Disabled('windows', 'Drive')
    @decorators.Disabled('wheel')
    @decorators.Disabled('windows')
    class Honda(object):
      pass
    self.assertEquals({'wheel', 'Drive', 'windows'}, Honda._disabled_strings)

  def testDisabledStringOnMethod(self):
    class Ford(object):
      @decorators.Disabled('windshield')
      def Drive(self):
        pass
    self.assertEquals({'windshield'}, Ford().Drive._disabled_strings)

    class Honda(object):
      @decorators.Disabled('windows', 'Drive')
      @decorators.Disabled('wheel')
      @decorators.Disabled('windows')
      def Drive(self):
        pass
    self.assertEquals({'wheel', 'Drive', 'windows'},
                      Honda().Drive._disabled_strings)

class TestEnableDecorators(unittest.TestCase):

  def testEnabledStringOnFunction(self):
    @decorators.Enabled('minus', 'power')
    def Sum():
      return 1 + 1
    self.assertEquals({'minus', 'power'}, Sum._enabled_strings)

    @decorators.Enabled('dot')
    @decorators.Enabled('product')
    @decorators.Enabled('product', 'dot')
    def Product():
      return 1 * 1
    self.assertEquals({'dot', 'product'}, Product._enabled_strings)

  def testEnabledStringOnClass(self):
    @decorators.Enabled('windshield', 'light')
    class Ford(object):
      pass
    self.assertEquals({'windshield', 'light'}, Ford._enabled_strings)

    @decorators.Enabled('wheel', 'Drive')
    @decorators.Enabled('wheel')
    @decorators.Enabled('windows')
    class Honda(object):
      pass
    self.assertEquals({'wheel', 'Drive', 'windows'}, Honda._enabled_strings)

  def testEnabledStringOnMethod(self):
    class Ford(object):
      @decorators.Enabled('windshield')
      def Drive(self):
        pass
    self.assertEquals({'windshield'}, Ford().Drive._enabled_strings)

    class Honda(object):
      @decorators.Enabled('windows', 'Drive')
      @decorators.Enabled('wheel', 'Drive')
      @decorators.Enabled('windows')
      def Drive(self):
        pass
    self.assertEquals({'wheel', 'Drive', 'windows'},
                      Honda().Drive._enabled_strings)


class TestShouldSkip(unittest.TestCase):
  def testEnabledStrings(self):
    test = FakeTest()
    possible_browser = FakePossibleBrowser()

    # When no enabled_strings is given, everything should be enabled.
    self.assertFalse(decorators.ShouldSkip(test, possible_browser)[0])

    test.SetEnabledStrings(['os_name'])
    self.assertFalse(decorators.ShouldSkip(test, possible_browser)[0])

    test.SetEnabledStrings(['another_os_name'])
    self.assertTrue(decorators.ShouldSkip(test, possible_browser)[0])

    test.SetEnabledStrings(['os_version_name'])
    self.assertFalse(decorators.ShouldSkip(test, possible_browser)[0])

    test.SetEnabledStrings(['os_name', 'another_os_name'])
    self.assertFalse(decorators.ShouldSkip(test, possible_browser)[0])

    test.SetEnabledStrings(['another_os_name', 'os_name'])
    self.assertFalse(decorators.ShouldSkip(test, possible_browser)[0])

    test.SetEnabledStrings(['another_os_name', 'another_os_version_name'])
    self.assertTrue(decorators.ShouldSkip(test, possible_browser)[0])

  def testDisabledStrings(self):
    test = FakeTest()
    possible_browser = FakePossibleBrowser()

    # When no disabled_strings is given, nothing should be disabled.
    self.assertFalse(decorators.ShouldSkip(test, possible_browser)[0])

    test.SetDisabledStrings(['os_name'])
    self.assertTrue(decorators.ShouldSkip(test, possible_browser)[0])

    test.SetDisabledStrings(['another_os_name'])
    self.assertFalse(decorators.ShouldSkip(test, possible_browser)[0])

    test.SetDisabledStrings(['os_version_name'])
    self.assertTrue(decorators.ShouldSkip(test, possible_browser)[0])

    test.SetDisabledStrings(['os_name', 'another_os_name'])
    self.assertTrue(decorators.ShouldSkip(test, possible_browser)[0])

    test.SetDisabledStrings(['another_os_name', 'os_name'])
    self.assertTrue(decorators.ShouldSkip(test, possible_browser)[0])

    test.SetDisabledStrings(['another_os_name', 'another_os_version_name'])
    self.assertFalse(decorators.ShouldSkip(test, possible_browser)[0])


class TestDeprecation(unittest.TestCase):

  @mock.patch('warnings.warn')
  def testFunctionDeprecation(self, warn_mock):
    @decorators.Deprecated(2015, 12, 1)
    def Foo(x):
      return x
    Foo(1)
    warn_mock.assert_called_with(
        'Function Foo is deprecated. It will no longer be supported on '
        'December 01, 2015. Please remove it or switch to an alternative '
        'before that time. \n', stacklevel=4)

  @mock.patch('warnings.warn')
  def testMethodDeprecated(self, warn_mock):

    class Bar(object):
      @decorators.Deprecated(2015, 12, 1, 'Testing only.')
      def Foo(self, x):
        return x

    Bar().Foo(1)
    warn_mock.assert_called_with(
        'Function Foo is deprecated. It will no longer be supported on '
        'December 01, 2015. Please remove it or switch to an alternative '
        'before that time. Testing only.\n', stacklevel=4)

  @mock.patch('warnings.warn')
  def testClassWithoutInitDefinedDeprecated(self, warn_mock):
    @decorators.Deprecated(2015, 12, 1)
    class Bar(object):
      def Foo(self, x):
        return x

    Bar().Foo(1)
    warn_mock.assert_called_with(
        'Class Bar is deprecated. It will no longer be supported on '
        'December 01, 2015. Please remove it or switch to an alternative '
        'before that time. \n', stacklevel=4)

  @mock.patch('warnings.warn')
  def testClassWithInitDefinedDeprecated(self, warn_mock):

    @decorators.Deprecated(2015, 12, 1)
    class Bar(object):
      def __init__(self):
        pass
      def Foo(self, x):
        return x

    Bar().Foo(1)
    warn_mock.assert_called_with(
        'Class Bar is deprecated. It will no longer be supported on '
        'December 01, 2015. Please remove it or switch to an alternative '
        'before that time. \n', stacklevel=4)

  @mock.patch('warnings.warn')
  def testInheritedClassDeprecated(self, warn_mock):
    class Ba(object):
      pass

    @decorators.Deprecated(2015, 12, 1)
    class Bar(Ba):
      def Foo(self, x):
        return x

    class Baz(Bar):
      pass

    Baz().Foo(1)
    warn_mock.assert_called_with(
        'Class Bar is deprecated. It will no longer be supported on '
        'December 01, 2015. Please remove it or switch to an alternative '
        'before that time. \n', stacklevel=4)

  def testReturnValue(self):
    class Bar(object):
      @decorators.Deprecated(2015, 12, 1, 'Testing only.')
      def Foo(self, x):
        return x

    self.assertEquals(5, Bar().Foo(5))
