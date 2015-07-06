# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Operations for updating test owners.

We want to allow editing test ownership through incoming chart metadata as well
as through dashboard UI, so we keep track of changes in test ownership that come
in from incoming chart metadata and apply them to a master copy of the test
owners data.  The dashboard UI, on the other hand, can modify the master copy
directly.

Test owners data are stored in layered_cache as dictionary of test suite path to
set of its owners' email.
  {
      'a/a': {'a@foo.com'},
      'b/b': {'b@foo.com'},
  }
"""

from dashboard import layered_cache

# Cache keys for layered cache test owner dictionary.
_CHARTJSON_OWNER_CACHE_KEY = 'ChartjsonOwner'
_MASTER_OWNER_CACHE_KEY = 'MasterOwner'

_MAX_TEST_SUITE_PATH_LENGTH = 500
_MAX_OWNER_EMAIL_LENGTH = 254


def UpdateOwnerFromChartjson(owner_dict):
  """Updates test owners with test owner data from chartjson.

  Checks if tests owners have changed by matching |owner_dict| with the stored
  owner dict for chartjson and update the master owner dict accordingly.

  Args:
    owner_dict: A dictionary of Master/Test suite to set of owners.
  """
  add_owner_dict = {}
  remove_owner_dict = {}
  owner_dict_cache = layered_cache.GetExternal(_CHARTJSON_OWNER_CACHE_KEY) or {}

  for path, owners in owner_dict.iteritems():
    owners = owners or set()
    owners_cache = owner_dict_cache.get(path, set())
    if owners_cache:
      diff = owners_cache - owners
      if diff:
        remove_owner_dict[path] = diff
      diff = owners - owners_cache
      if diff:
        add_owner_dict[path] = diff
    else:
      add_owner_dict[path] = owners

    if owners:
      owner_dict_cache[path] = owners
    elif path in owner_dict_cache:
      del owner_dict_cache[path]

  if add_owner_dict or remove_owner_dict:
    layered_cache.SetExternal(_CHARTJSON_OWNER_CACHE_KEY, owner_dict_cache)
  if add_owner_dict:
    AddOwnerFromDict(add_owner_dict)
  if remove_owner_dict:
    RemoveOwnerFromDict(remove_owner_dict)


def AddOwner(test_suite_path, owner_email):
  """Adds an owner for a test suite path.

  Args:
    test_suite_path: A string of "Master/Test suite".
    owner_email: An email string.
  """
  owner_dict_cache = GetMasterCachedOwner()
  owners = owner_dict_cache.get(test_suite_path, set())
  owners.add(owner_email)
  owner_dict_cache[test_suite_path] = owners
  layered_cache.SetExternal(_MASTER_OWNER_CACHE_KEY, owner_dict_cache)
  owner_dict_cache = GetMasterCachedOwner()


def AddOwnerFromDict(owner_dict):
  """Adds test owner from |owner_dict| to owner dict in layered_cache.

  For example, if owner cache dict is:
    {
        'a/a': {'a@foo.com'},
        'a/b': {'b@foo.com'},
    }
  and parameter owner_dict is:
    {
        'a/a': {'c@foo.com'},
        'c/c': {'c@foo.com'},
    }
  then the cached will be updated to:
    {
        'a/a': {'a@foo.com', 'c@foo.com'},
        'a/b': {'b@foo.com'},
        'c/c': {'c@foo.com'},
    }

  Args:
    owner_dict: A dictionary of "Master/Test suite" to set of owners' email.
  """
  owner_dict_cache = GetMasterCachedOwner()
  for path, owners in owner_dict.iteritems():
    owners_cache = owner_dict_cache.get(path, set())
    owners_cache.update(owners)
    owner_dict_cache[path] = owners_cache
  layered_cache.SetExternal(_MASTER_OWNER_CACHE_KEY, owner_dict_cache)


def RemoveOwner(test_suite_path, owner_email=None):
  """Removes test owners for |test_suite_path|.

  Args:
    test_suite_path: A string of "Master/Test suite".
    owner_email: Optional email string.  If not specified, dict entry
        for |test_suite_path| will be deleted.
  """
  owner_dict_cache = GetMasterCachedOwner()
  if test_suite_path in owner_dict_cache:
    if owner_email:
      owners = owner_dict_cache[test_suite_path]
      owners.remove(owner_email)
      if not owners:
        del owner_dict_cache[test_suite_path]
    else:
      del owner_dict_cache[test_suite_path]
  layered_cache.SetExternal(_MASTER_OWNER_CACHE_KEY, owner_dict_cache)


def RemoveOwnerFromDict(owner_dict):
  """Adds test owner from |owner_dict| to owner dict in layered_cache.

  Args:
    owner_dict: A dictionary of Master/Test suite to set of owners to be
        removed.
  """
  owner_dict_cache = GetMasterCachedOwner()
  for path, owners in owner_dict.iteritems():
    owners_cache = owner_dict_cache.get(path, set())
    owner_dict_cache[path] = owners_cache - owners
    if not owner_dict_cache[path]:
      del owner_dict_cache[path]
  layered_cache.SetExternal(_MASTER_OWNER_CACHE_KEY, owner_dict_cache)


def GetOwners(test_suite_paths):
  """Gets a list of owners for a list of test suite paths."""
  owners = set()
  owner_dict_cache = GetMasterCachedOwner()
  for path in test_suite_paths:
    if path in owner_dict_cache:
      owners.update(owner_dict_cache[path])
  return sorted(owners)


def GetTestSuitePaths(owner_email):
  """Gets a list of test suite paths for an owner."""
  test_suite_paths = []
  owner_dict_cache = GetMasterCachedOwner()
  for path, owners in owner_dict_cache.iteritems():
    if owner_email in owners:
      test_suite_paths.append(path)
  return sorted(test_suite_paths)


def GetMasterCachedOwner():
  """Gets test owner cached dictionary from layered_cache."""
  return layered_cache.GetExternal(_MASTER_OWNER_CACHE_KEY) or {}


def ValidateTestSuitePath(test_suite_path):
  if test_suite_path and len(test_suite_path) > _MAX_TEST_SUITE_PATH_LENGTH:
    raise ValueError('Test suite path is too long: %s.' % test_suite_path)


def ValidateOwnerEmail(owner_email):
  if owner_email and len(owner_email) > _MAX_OWNER_EMAIL_LENGTH:
    raise ValueError('Owner\'s email is too long: %s.' % owner_email)
