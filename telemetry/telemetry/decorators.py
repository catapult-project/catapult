# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
# pylint: disable=W0212

import functools
import inspect
import types


def Cache(obj):
  """Decorator for caching read-only properties.

  Example usage (always returns the same Foo instance):
    @Cache
    def CreateFoo():
      return Foo()

  If CreateFoo() accepts parameters, a separate cached value is maintained
  for each unique parameter combination.

  Cached methods maintain their cache for the lifetime of the /instance/, while
  cached functions maintain their cache for the lifetime of the /module/.
  """
  @functools.wraps(obj)
  def Cacher(*args, **kwargs):
    cacher = args[0] if inspect.getargspec(obj).args[:1] == ['self'] else obj
    cacher.__cache = cacher.__cache if hasattr(cacher, '__cache') else {}
    key = str(obj) + str(args) + str(kwargs)
    if key not in cacher.__cache:
      cacher.__cache[key] = obj(*args, **kwargs)
    return cacher.__cache[key]
  return Cacher


def Disabled(*args):
  """Decorator for disabling tests/benchmarks.

  May be used without args to unconditionally disable:
    @Disabled  # Unconditionally disabled.

  If args are given, the test will be disabled if ANY of the args match the
  browser type, OS name or OS version:
    @Disabled('canary')        # Disabled for canary browsers
    @Disabled('win')           # Disabled on Windows.
    @Disabled('win', 'linux')  # Disabled on both Windows and Linux.
    @Disabled('mavericks')     # Disabled on Mac Mavericks (10.9) only.
  """
  def _Disabled(func):
    if not isinstance(func, types.FunctionType):
      func._disabled_strings = disabled_strings
      return func
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
      func(*args, **kwargs)
    wrapper._disabled_strings = disabled_strings
    return wrapper
  if len(args) == 1 and callable(args[0]):
    disabled_strings = []
    return _Disabled(args[0])
  disabled_strings = list(args)
  for disabled_string in disabled_strings:
    # TODO(tonyg): Validate that these strings are recognized.
    assert isinstance(disabled_string, str), '@Disabled accepts a list of strs'
  return _Disabled


def Enabled(*args):
  """Decorator for enabling tests/benchmarks.

  The test will be enabled if ANY of the args match the browser type, OS name
  or OS version:
    @Enabled('canary')        # Enabled only for canary browsers
    @Enabled('win')           # Enabled only on Windows.
    @Enabled('win', 'linux')  # Enabled only on Windows or Linux.
    @Enabled('mavericks')     # Enabled only on Mac Mavericks (10.9).
  """
  def _Enabled(func):
    if not isinstance(func, types.FunctionType):
      func._enabled_strings = enabled_strings
      return func
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
      func(*args, **kwargs)
    wrapper._enabled_strings = enabled_strings
    return wrapper
  assert args and not callable(args[0]), '@Enabled requires argumentas'
  enabled_strings = list(args)
  for enabled_string in enabled_strings:
    # TODO(tonyg): Validate that these strings are recognized.
    assert isinstance(enabled_string, str), '@Enabled accepts a list of strs'
  return _Enabled


def IsEnabled(test, possible_browser):
  """Returns True iff |test| is enabled given the |possible_browser|.

  Use to respect the @Enabled / @Disabled decorators.

  Args:
    test: A function or class that may contain _disabled_strings and/or
          _enabled_strings attributes.
    possible_browser: A PossibleBrowser to check whether |test| may run against.
  """
  platform_attributes = [a.lower() for a in [
      possible_browser.browser_type,
      possible_browser.platform.GetOSName(),
      possible_browser.platform.GetOSVersionName(),
      ]]
  if possible_browser.supports_tab_control:
    platform_attributes.append('has tabs')

  if hasattr(test, '__name__'):
    name = test.__name__
  elif hasattr(test, '__class__'):
    name = test.__class__.__name__
  else:
    name = str(test)

  if hasattr(test, '_disabled_strings'):
    disabled_strings = test._disabled_strings
    if not disabled_strings:
      return False  # No arguments to @Disabled means always disable.
    for disabled_string in disabled_strings:
      if disabled_string in platform_attributes:
        print (
            'Skipping %s because it is disabled for %s. '
            'You are running %s.' % (name,
                                     ' and '.join(disabled_strings),
                                     ' '.join(platform_attributes)))
        return False

  if hasattr(test, '_enabled_strings'):
    enabled_strings = test._enabled_strings
    if not enabled_strings:
      return True  # No arguments to @Enabled means always enable.
    for enabled_string in enabled_strings:
      if enabled_string in platform_attributes:
        return True
    print (
        'Skipping %s because it is only enabled for %s. '
        'You are running %s.' % (name,
                                 ' or '.join(enabled_strings),
                                 ' '.join(platform_attributes)))
    return False

  return True
