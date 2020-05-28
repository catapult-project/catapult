# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""The database model Sheriff, for sheriff rotations."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from google.appengine.ext import ndb


class _Visibility(object):
  """Mirror of sheriff_pb2.Subscription.VisibilityTag."""
  # This needs to be kept in sync with sheriff_pb2.Subscription.VisibilityTag.
  # We don't import it here to avoid circular imports, especially as protobuf
  # imports involve fragile import hook hacks.
  INTERNAL_ONLY = 0
  PUBLIC = 1


VISIBILITY = _Visibility()


class Subscription(ndb.Model):
  """
  Configuration options for alerts' subscriber. It's a mapping to the
  Subscription protobuf and must never be directly stored to datastore.
  """
  _use_datastore = False

  revision = ndb.StringProperty()
  name = ndb.StringProperty()
  rotation_url = ndb.StringProperty()
  notification_email = ndb.StringProperty()
  bug_labels = ndb.StringProperty(repeated=True)
  bug_components = ndb.StringProperty(repeated=True)
  bug_cc_emails = ndb.StringProperty(repeated=True)
  visibility = ndb.IntegerProperty(default=VISIBILITY.INTERNAL_ONLY)
  auto_triage_enable = ndb.BooleanProperty()
  auto_bisect_enable = ndb.BooleanProperty()
  monorail_project_id = ndb.StringProperty(default='chromium')
