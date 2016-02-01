# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A bounded size logger that's save in datastore.

This logger keeps a fixed number of recent logs in FIFO behavior.  Logs are
stored by namespaced key in datastore.  Each log message has a size limit of
_MAX_MSG_SIZE.

Example:

  template = '{asctime} {message}{extra}'
  formatter = quick_logger.Formatter(template, extra='!')
  logger = quick_logger.QuickLogger('a_namespace', 'a_log_name', formatter)
  logger.Log('Hello %s', 'world')
  logger.Save()
"""

import collections
import cPickle as pickle
import logging
import time

from google.appengine.api import datastore_errors
from google.appengine.ext import ndb

# Maximum number of QuickLogPart entities to hold a log.
_MAX_NUM_PARTS = 4

# _MAX_NUM_RECORD * (number of serialized quick_logger.Record)
# should be less than App Engine 1MB BlobProperty size limit.
_MAX_NUM_RECORD = 64 * _MAX_NUM_PARTS
_MAX_MSG_SIZE = 12288  # 12KB


def Get(namespace, key, no_wait=True):
  """Gets list of Record from the datastore.

  Args:
    namespace: The namespace for key.
    key: The key name.
    no_wait: True to get results without waiting for datastore to apply
             pending changes, False otherwise.

  Returns:
    List of Record, None if key does not exist in datastore.
  """
  namespaced_key = '%s__%s' % (namespace, key)
  key = ndb.Key('QuickLog', namespaced_key)
  if no_wait:
    quick_log = key.get(read_policy=ndb.EVENTUAL_CONSISTENCY)
  else:
    quick_log = key.get()
  if quick_log:
    return quick_log.GetRecords()
  return None


def Delete(namespace, key):
  """Delete a log entity from the datastore.

  Args:
    namespace: The namespace for key.
    key: The key name.
  """
  namespaced_key = '%s__%s' % (namespace, key)
  ndb.Key('QuickLog', namespaced_key).delete()


def _Set(namespace, key, records):
  """Sets list of Record in the datastore.

  Args:
    namespace: A string namespace for the key.
    key: A string key name which will be namespaced for QuickLog entity key.
    records: List of Record entities.
  """
  namespaced_key = '%s__%s' % (namespace, key)
  try:
    log = QuickLog(id=namespaced_key, namespace=namespace)
    log.SetRecords(namespaced_key, records)
  except datastore_errors.BadRequestError as e:
    logging.warning('BadRequestError for namespaced key %s: %s',
                    namespaced_key, e)


class QuickLog(ndb.Model):
  """Represents a log entity."""

  # Namespace for identifying logs.
  namespace = ndb.StringProperty(indexed=True)

  # The time log was first created.
  timestamp = ndb.DateTimeProperty(indexed=True, auto_now_add=True)

  # Number of entities use to store records.
  size = ndb.IntegerProperty(default=0)

  def GetRecords(self):
    """Gets records store in multiple entities.

    Combines and deserializes the data stored in QuickLogPart for this log.

    Returns:
      List of Record object.
    """
    if not self.key.id():
      logging.error('Key id does not exist.')
      return None
    if self.size < 1:
      return None

    string_id = self.key.string_id()
    log_part_keys = [ndb.Key('QuickLog', string_id, 'QuickLogPart', i + 1)
                     for i in xrange(self.size)]
    log_parts = ndb.get_multi(log_part_keys)
    serialized = ''.join(l.value for l in log_parts if l is not None)
    try:
      return pickle.loads(serialized)
    except ImportError:
      logging.error('Failed to load QuickLog "%s".', string_id)
    return None

  def SetRecords(self, key, records):
    """Sets records for this log and put into datastore.

    Serializes records and save over multiple entities if necessary.

    Args:
      key: String key name of a QuickLog entity.
      records: List of Record object.
    """
    # Number of bytes less than 1MB for ndb.BlobProperty.
    chunk_size = 1000000
    serialized = pickle.dumps(records, 2)
    length = len(serialized)
    if length / chunk_size > _MAX_NUM_PARTS:
      logging.error('Data too large to save.')
      return None

    log_parts = []
    for i in xrange(0, length, chunk_size):
      # +1 to start entity key at 1.
      part_id = i // chunk_size + 1
      part_value = serialized[i:i + chunk_size]
      parent_key = ndb.Key('QuickLog', key)
      log_part = QuickLogPart(id=part_id, parent=parent_key, value=part_value)
      log_parts.append(log_part)

    self.size = len(log_parts)
    ndb.put_multi(log_parts + [self])


class QuickLogPart(ndb.Model):
  """Holds a part of serialized data for a log.

  This entity key has the form:
    nbd.Key('QuickLog', quick_log_id, 'QuickLogPart', log_part_index)
  """

  value = ndb.BlobProperty()


class Formatter(object):
  """Class specifying how to format a Record."""

  _datefmt = '%Y-%m-%d %H:%M:%S'

  def __init__(self, template=None, *args, **kwargs):
    """Initializes formatter.

    Args:
      template: String template which can contain placeholders for arguments
                in args, kwargs or supported attributes.
      *args: Replacement field for positional argument.
      **kwargs: Replacement field for keyword argument.
    """
    self._args = args
    self._kwargs = kwargs
    self._template = template
    if not self._template:
      self._template = '{asctime} {message}'

  def Format(self, record):
    """Format the record."""
    self._kwargs['message'] = record.message
    if '{asctime}' in self._template:
      lt = time.localtime(record.index)
      self._kwargs['asctime'] = time.strftime(self._datefmt, lt)
    record.message = self._template.format(*self._args, **self._kwargs)


# Not subclassing object (aka old-style class) reduces the serialization size.
class Record:  # pylint: disable=old-style-class
  """Class to hold a log."""

  def __init__(self, message):
    self.message = message
    self.index = time.time()


class QuickLogger(object):
  """Logger class."""

  def __init__(self, namespace, name, formatter=None):
    """Initializes logger.

    Args:
      namespace: The namespace of logger.
      name: Name of logger.
      formatter: Formatter object to format logs.
    """
    self._namespace = namespace
    self._name = name
    self._formatter = formatter
    self._records = collections.deque(maxlen=_MAX_NUM_RECORD)

  def Log(self, message, *args):
    """Add a message with 'message % args'.

    Must call Save() to save to datastore.

    Args:
      message: String message.
      *args: Replacement field for positional argument.
    """
    message = str(message)
    if args:
      message %= args
    record = Record(message)
    if self._formatter:
      self._formatter.Format(record)
    if len(record.message) > _MAX_MSG_SIZE:
      logging.error('Message must be less than (%s)', _MAX_MSG_SIZE)
      return
    self._records.appendleft(record)

  @ndb.transactional
  def Save(self):
    """Saves logs to datastore.

    Add transactional annotation to make this synchronous since we're reading
    then writing.
    """
    if not self._records:
      return
    records = list(self._records)
    stored_records = Get(self._namespace, self._name, no_wait=False)
    if stored_records:
      records.extend(stored_records)
    _Set(self._namespace, self._name, records[0:_MAX_NUM_RECORD])
    self._records.clear()
