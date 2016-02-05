# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A module for storing and getting objects from datastore.

This module provides Get, Set and Delete functions for storing pickleable
objects in datastore, with support for large objects greater than 1 MB.

Although this module contains ndb.Model classes, these are not intended
to be used directly by other modules.

App Engine datastore limits entity size to less than 1 MB; this module
supports storing larger objects by splitting the data and using multiple
datastore entities and multiple memcache keys. Using ndb.get and pickle, a
complex data structure can be retrieved more quickly than datastore fetch.

Example:
  john = Account()
  john.username = 'John'
  john.userid = 123
  stored_object.Set(john.userid, john)
"""

import cPickle as pickle
import logging

from google.appengine.api import memcache
from google.appengine.ext import ndb

_MULTIPART_ENTITY_MEMCACHE_KEY = 'multipart_entity_'

# Maximum number of entities and memcache to save a value.
# The limit for data stored in one datastore entity is 1 MB,
# and the limit for memcache batch operations is 32 MB. See:
# https://cloud.google.com/appengine/docs/python/memcache/#Python_Limits
_MAX_NUM_PARTS = 16

# Max bytes per entity or value cached with memcache.
_CHUNK_SIZE = 1000 * 1000


def Get(key):
  """Gets the value.

  Args:
    key: String key value.

  Returns:
    A value for key.
  """
  results = MultipartCache.Get(key)
  if not results:
    results = _GetValueFromDatastore(key)
    MultipartCache.Set(key, results)
  return results


def Set(key, value):
  """Sets the value in datastore and memcache with limit of '_MAX_NUM_PARTS' MB.

  Args:
    key: String key value.
    value: A pickleable value to be stored limited at '_MAX_NUM_PARTS' MB.
  """
  entity = ndb.Key(MultipartEntity, key).get()
  if not entity:
    entity = MultipartEntity(id=key)
  entity.SetData(value)
  entity.Save()
  MultipartCache.Set(key, value)


def Delete(key):
  """Deletes the value in datastore and memcache."""
  ndb.Key(MultipartEntity, key).delete()
  MultipartCache.Delete(key)


class MultipartEntity(ndb.Model):
  """Container for PartEntity."""

  # Number of entities use to store serialized.
  size = ndb.IntegerProperty(default=0, indexed=False)

  @classmethod
  def _post_get_hook(cls, key, future):  # pylint: disable=unused-argument
    """Deserializes data from multiple PartEntity."""
    entity = future.get_result()
    if entity is None or not entity.size:
      return

    string_id = entity.key.string_id()
    part_keys = [ndb.Key(MultipartEntity, string_id, PartEntity, i + 1)
                 for i in xrange(entity.size)]
    part_entities = ndb.get_multi(part_keys)
    serialized = ''.join(p.value for p in part_entities if p is not None)
    entity.SetData(pickle.loads(serialized))

  @classmethod
  def _pre_delete_hook(cls, key):
    """Deletes PartEntity entities."""
    part_keys = PartEntity.query(ancestor=key).fetch(keys_only=True)
    ndb.delete_multi(part_keys)

  def Save(self):
    """Stores serialized data over multiple PartEntity."""
    serialized_parts = _Serialize(self.GetData())
    if len(serialized_parts) > _MAX_NUM_PARTS:
      logging.error('Max number of parts reached.')
      return
    part_list = []
    num_parts = len(serialized_parts)
    for i in xrange(num_parts):
      if serialized_parts[i] is not None:
        part = PartEntity(id=i + 1, parent=self.key, value=serialized_parts[i])
        part_list.append(part)
    self.size = num_parts
    ndb.put_multi(part_list + [self])

  def GetData(self):
    return getattr(self, '_data', None)

  def SetData(self, data):
    setattr(self, '_data', data)


class PartEntity(ndb.Model):
  """Holds a part of serialized data for MultipartEntity.

  This entity key has the form:
    ndb.Key('MultipartEntity', multipart_entity_id, 'PartEntity', part_index)
  """
  value = ndb.BlobProperty()


class MultipartCache(object):
  """Contains operations for storing values over multiple memcache keys.

  Values are serialized, split, and stored over multiple memcache keys.  The
  head cache stores the expected size.
  """

  @classmethod
  def Get(cls, key):
    """Gets value in memcache."""
    keys = cls._GetCacheKeyList(key)
    head_key = cls._GetCacheKey(key)
    cache_values = memcache.get_multi(keys)
    # Whether we have all the memcache values.
    if len(keys) != len(cache_values) or head_key not in cache_values:
      return None

    serialized = ''
    cache_size = cache_values[head_key]
    keys.remove(head_key)
    for key in keys[:cache_size]:
      if key not in cache_values:
        return None
      if cache_values[key] is not None:
        serialized += cache_values[key]
    return pickle.loads(serialized)

  @classmethod
  def Set(cls, key, value):
    """Sets a value in memcache."""
    serialized_parts = _Serialize(value)
    if len(serialized_parts) > _MAX_NUM_PARTS:
      logging.error('Max number of parts reached.')
      return

    cached_values = {}
    cached_values[cls._GetCacheKey(key)] = len(serialized_parts)
    for i in xrange(len(serialized_parts)):
      cached_values[cls._GetCacheKey(key, i)] = serialized_parts[i]
    memcache.set_multi(cached_values)

  @classmethod
  def Delete(cls, key):
    """Deletes all cached values for key."""
    memcache.delete_multi(cls._GetCacheKeyList(key))

  @classmethod
  def _GetCacheKeyList(cls, key):
    """Gets a list of head cache key and cache key parts."""
    keys = [cls._GetCacheKey(key, i) for i in xrange(_MAX_NUM_PARTS)]
    keys.append(cls._GetCacheKey(key))
    return keys

  @classmethod
  def _GetCacheKey(cls, key, index=None):
    """Returns either head cache key or cache key part."""
    if index is not None:
      return _MULTIPART_ENTITY_MEMCACHE_KEY + '%s.%s' % (key, index)
    return _MULTIPART_ENTITY_MEMCACHE_KEY + key


def _GetValueFromDatastore(key):
  entity = ndb.Key(MultipartEntity, key).get()
  if not entity:
    return None
  return entity.GetData()


def _Serialize(value):
  """Serializes value and returns a list of its parts.

  Args:
    value: A pickleable value.

  Returns:
    A list of string representation of the value that has been pickled and split
    into _CHUNK_SIZE.
  """
  serialized = pickle.dumps(value, 2)
  length = len(serialized)
  values = []
  for i in xrange(0, length, _CHUNK_SIZE):
    values.append(serialized[i:i + _CHUNK_SIZE])
  for i in xrange(len(values), _MAX_NUM_PARTS):
    values.append(None)
  return values
