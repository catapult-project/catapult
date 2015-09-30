#!/usr/bin/env python
#
# Copyright 2010 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import cStringIO
import logging
import os

from protorpc import descriptor
from protorpc import messages
from protorpc import protobuf
from protorpc import remote
from protorpc import stub

from google.appengine.api import memcache
from google.appengine.ext.appstats import recording


# Import contents of appstats.descriptor in to this module from binary appstats
# protobuf descriptor.  Definitions are imported into module apphosting.
stub.import_file_set(os.path.join(os.path.dirname(__file__),
                                  'appstats.descriptor'))
import apphosting


class Summary(messages.Message):
  """Response for AppStatsService.get_summary.

  Fields:
    stats: List of RequestStatProto objects summarizing application activity.
  """

  stats = messages.MessageField(apphosting.RequestStatProto, 1, repeated=True)


class GetDetailsRequest(messages.Message):
  """Request for AppStatsService.get_details.

  Fields:
    timestamp: Timestamp of appstats detail to retrieve.
  """

  timestamp = messages.IntegerField(1, required=True)


class Details(messages.Message):
  """Response for AppStatsService.get_details.

  Fields:
    stat: Individual stat details if found, else None.
  """

  stat = messages.MessageField(apphosting.RequestStatProto, 1)


# TODO(rafek): Remove this function when recording.load_summary_protos is
# refactored in the App Engine SDK.
def load_summary_protos():
  """Load all valid summary records from memcache.

  Returns:
    A list of RequestStatProto instances, in reverse chronological order
    (i.e. most recent first).

  NOTE: This is limited to returning at most config.KEY_MODULUS records,
  since there are only that many distinct keys.  See also make_key().
  """
  tmpl = '%s%s%s' % (recording.config.KEY_PREFIX,
                     recording.config.KEY_TEMPLATE,
                     recording.config.PART_SUFFIX)
  keys = [tmpl % i
          for i in
          range(0, recording.config.KEY_DISTANCE * recording.config.KEY_MODULUS,
                recording.config.KEY_DISTANCE)]
  results = memcache.get_multi(keys, namespace=recording.config.KEY_NAMESPACE)
  records = []
  for rec in results.itervalues():
    try:
      pb = protobuf.decode_message(apphosting.RequestStatProto, rec)
    except Exception, err:
      logging.warn('Bad record: %s', err)
    else:
      records.append(pb)
  logging.info('Loaded %d raw records, %d valid', len(results), len(records))
  # Sorts by time, newest first.
  records.sort(key=lambda pb: -pb.start_timestamp_milliseconds)
  return records


# TODO(rafek): Remove this function when recording.load_full_protos is
# refactored in the App Engine SDK.
def load_full_proto(timestamp):
  """Load the full record for a given timestamp.

  Args:
    timestamp: The start_timestamp of the record, as a float in seconds
      (see make_key() for details).

  Returns:
    A RequestStatProto instance if the record exists and can be loaded;
    None otherwise.
  """
  full_key = recording.make_key(timestamp) + recording.config.FULL_SUFFIX
  full_binary = memcache.get(full_key, namespace=recording.config.KEY_NAMESPACE)
  if full_binary is None:
    logging.info('No full record at %s', full_key)
    return None
  try:
    full = protobuf.decode_message(apphosting.RequestStatProto, full_binary)
  except Exception, err:
    logging.warn('Bad full record at %s: %s', full_key, err)
    return None
  if full.start_timestamp_milliseconds != int(timestamp * 1000):
    logging.warn('Hash collision, record at %d has timestamp %d',
                 int(timestamp * 1000), full.start_timestamp_milliseconds)
    return None  # Hash collision -- the requested record no longer exists.
  return full


class AppStatsService(remote.Service):
  """Service for getting access to AppStats data."""

  @remote.method(response_type=Summary)
  def get_summary(self, request):
    """Get appstats summary."""
    response = Summary()

    response.stats = load_summary_protos()

    return response

  @remote.method(GetDetailsRequest, Details)
  def get_details(self, request):
    """Get appstats details for a particular timestamp."""
    response = Details()
    recording_timestamp = request.timestamp * 0.001
    logging.error('Fetching recording from %f', recording_timestamp)
    response.stat = load_full_proto(recording_timestamp)
    return response
