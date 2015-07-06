# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""General functions which are useful throughout this project."""

import re
import time

from google.appengine.ext import ndb

from dashboard import request_handler


def TestPath(key):
  """Returns the test path for a Test from an ndb.Key.

  A "test path" is just a convenient string representation of an ndb.Key.
  Each test path corresponds to one ndb.Key, which can be used to get an
  entity.

  Args:
    key: An ndb.Key where all IDs are string IDs.

  Returns:
    A test path string.
  """
  return '/'.join(key.flat()[1::2])


def TestSuiteName(test_key):
  """Returns the test suite name for a given Test key."""
  pairs = test_key.pairs()
  if len(pairs) < 3:
    return None
  return pairs[2][1]


def TestKey(test_path):
  """Returns the ndb.Key that corresponds to a test path."""
  if test_path is None:
    return None
  path_parts = test_path.split('/')
  if path_parts is None:
    return None
  key_list = [('Master', path_parts[0])]
  if len(path_parts) > 1:
    key_list += [('Bot', path_parts[1])]
  if len(path_parts) > 2:
    key_list += [('Test', x) for x in path_parts[2:]]
  return ndb.Key(pairs=key_list)


def TestMatchesPattern(test, pattern):
  """Checks whether a test matches a test path pattern.

  Args:
    test: A Test entity or a Test key.
    pattern: A test path which can include wildcard characters (*).

  Returns:
    True if it matches, False otherwise.
  """
  if not test:
    return False
  if type(test) is ndb.Key:
    test_path = TestPath(test)
  else:
    test_path = test.test_path
  test_path_parts = test_path.split('/')
  pattern_parts = pattern.split('/')
  if len(test_path_parts) != len(pattern_parts):
    return False
  for test_path_part, pattern_part in zip(test_path_parts, pattern_parts):
    if not _MatchesPatternPart(pattern_part, test_path_part):
      return False
  return True


def _MatchesPatternPart(pattern_part, test_path_part):
  """Checks whether a pattern (possibly with a *) matches the given string.

  Args:
    pattern_part: A string which may contain a wildcard (*).
    test_path_part: Another string.

  Returns:
    True if it matches, False otherwise.
  """
  if pattern_part == '*' or pattern_part == test_path_part:
    return True
  if '*' not in pattern_part:
    return False
  # Escape any other special non-alphanumeric characters.
  pattern_part = re.escape(pattern_part)
  # There are not supposed to be any other asterisk characters, so all
  # occurrences of backslash-asterisk can now be replaced with dot-asterisk.
  re_pattern = re.compile('^' + pattern_part.replace('\\*', '.*') + '$')
  return re_pattern.match(test_path_part)


def TimestampMilliseconds(datetime):
  """Returns the number of milliseconds since the epoch."""
  return int(time.mktime(datetime.timetuple()) * 1000)


def GetTestContainerKey(test):
  """Gets the TestContainer key for the given Test.

  Args:
    test: Either a Test entity or its ndb.Key.

  Returns:
    ndb.Key('TestContainer', test path)
  """
  test_path = None
  if type(test) is ndb.Key:
    test_path = TestPath(test)
  else:
    test_path = test.test_path
  return ndb.Key('TestContainer', test_path)


def GetMulti(keys):
  """Gets a list of entities from a list of keys.

  If this user is logged in, this is the same as ndb.get_multi. However, if the
  user is logged out and any of the data is internal only, an AssertionError
  will be raised.

  Args:
    keys: A list of ndb entity keys.

  Returns:
    A list of entities, but no internal_only ones if the user is not logged in.
  """
  if request_handler.IsLoggedInWithGoogleAccount():
    return ndb.get_multi(keys)
  # Not logged in. Check each key individually.
  entities = []
  for key in keys:
    try:
      entities.append(key.get())
    except AssertionError:
      continue
  return entities
