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

import uuid

import collections
import cPickle as pickle
import logging
import time

from google.appengine.ext import ndb

# Maximum number of QuickLogPart entities to hold a log.
_MAX_NUM_PARTS = 4

# _MAX_NUM_RECORD * (number of serialized quick_logger.Record)
# should be less than App Engine 1MB BlobProperty size limit.
_MAX_NUM_RECORD = 64 * _MAX_NUM_PARTS
_MAX_MSG_SIZE = 12288  # 12KB


def Get(namespace, key):
  """Gets list of Record from the datastore.

  Args:
    namespace: The namespace for key.
    key: The key name.

  Returns:
    List of Record, None if key does not exist in datastore.
  """
  quick_log = _GetQuickLog(namespace, key)
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


def _GetQuickLog(namespace, key):
  """Gets QuickLog entity from a namespace and a key."""
  namespaced_key = '%s__%s' % (namespace, key)
  key = ndb.Key('QuickLog', namespaced_key)
  return key.get()


def _CreateQuickLog(namespace, key):
  """Creates an empty QuickLog entity."""
  namespaced_key = '%s__%s' % (namespace, key)
  log = QuickLog(id=namespaced_key)
  log.put()
  return log


class QuickLog(ndb.Model):
  """Represents a log entity."""

  # Used for querying existing logs.
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

  def SetRecords(self, records):
    """Sets records for this log and put into datastore.

    Serializes records and save over multiple entities if necessary.

    Args:
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
      log_part = QuickLogPart(id=part_id, parent=self.key, value=part_value)
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
    """Formats a record."""
    self._kwargs['message'] = record.message
    if '{asctime}' in self._template:
      # Support backward compatibility.
      timestamp = getattr(record, 'timestamp', record.index)
      lt = time.localtime(timestamp)
      self._kwargs['asctime'] = time.strftime(self._datefmt, lt)
    record.message = self._template.format(*self._args, **self._kwargs)


# Not subclassing object (aka old-style class) reduces the serialization size.
class Record:  # pylint: disable=old-style-class, invalid-name
  """Class to hold a log.

  Properties:
    message: A string.
    id: A string ID.
    timestamp: Seconds since the epoch which represents time when record was
        created.
  """

  def __init__(self, message, record_id):
    self.message = message
    self.id = record_id
    self.timestamp = time.time()
    self.index = None  # Deprecated.  Remove this when we migrate old Records.

class QuickLogger(object):
  """Logger class."""

  def __init__(self, namespace, name, formatter=None):
    """Initializes logger.

    Args:
      namespace: The namespace of logger.
      name: Name of logger.
      formatter: Formatter object to format logs.
    """
    self._formatter = formatter
    self._records = collections.deque(maxlen=_MAX_NUM_RECORD)
    self._record_count = 0
    self._log = _GetQuickLog(namespace, name)
    if not self._log:
      self._log = _CreateQuickLog(namespace, name)
    self._unique_id = uuid.uuid1().hex


  def Log(self, message, record_id=None):
    """Adds or updates a log record.

    After this is called, Save() must be called to save to datastore.

    Args:
      message: String message.
      record_id: ID of the record to update; if None, add a new record.

    Returns:
      The ID of updated or created Record.
    """
    message = str(message)
    record = self._CreateRecord(message, record_id)
    if self._formatter:
      self._formatter.Format(record)
    if len(record.message) > _MAX_MSG_SIZE:
      logging.error('Message must be less than (%s)', _MAX_MSG_SIZE)
      return
    self._records.appendleft(record)
    return record.id

  @ndb.transactional
  def Save(self):
    """Saves logs to datastore.

    Add transactional annotation to make this synchronous since we're reading
    then writing.
    """
    if not self._records:
      return
    records = list(self._records)
    stored_records = self._log.GetRecords()
    self._MergeRecords(records, stored_records)
    self._log.SetRecords(records[0:_MAX_NUM_RECORD])
    self._records.clear()

  def _CreateRecord(self, message, record_id=None):
    if not record_id:
      return Record(message, self._CreateRecordId())

    for record in list(self._records):
      if getattr(record, 'id', None) == record_id:
        self._records.remove(record)
        return Record(message, record_id)
    # If index provided doesn't exist, we'll create a log with this index.
    return Record(message, record_id)

  def _CreateRecordId(self):
    """Creates an ID for a Record.

    A record's ID is the current record count namespaced by self._unique_id.
    """
    self._record_count += 1
    return '%s_%s' % (self._unique_id, self._record_count)

  def _MergeRecords(self, records, stored_records):
    """Updates |records| with stored records if id does not already exist."""
    if not stored_records:
      return
    new_ids = {r.id for r in records}
    records.extend(r for r in stored_records
                   if getattr(r, 'id', None) not in new_ids)
