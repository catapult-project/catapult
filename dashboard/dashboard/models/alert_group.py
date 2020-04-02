# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""The database model for an "Anomaly", which represents a step up or down."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from dashboard.models import anomaly
from google.appengine.ext import ndb


class RevisionRange(ndb.Model):
  repository = ndb.StringProperty()
  start = ndb.IntegerProperty()
  end = ndb.IntegerProperty()

  def IsOverlapping(self, b):
    if not b or self.repository != b.repository:
      return False
    return max(self.start, b.start) < min(self.end, b.end)


class BugInfo(ndb.Model):
  project = ndb.StringProperty()
  bug_id = ndb.IntegerProperty()


class AlertGroup(ndb.Model):
  name = ndb.StringProperty(indexed=True)
  created = ndb.DateTimeProperty(indexed=False, auto_now_add=True)
  updated = ndb.DateTimeProperty(indexed=False, auto_now_add=True)

  class Status(object):
    unknown = 0
    untriaged = 1
    triaged = 2
    bisected = 3
    closed = 4

  status = ndb.IntegerProperty(indexed=False)
  active = ndb.BooleanProperty(indexed=True)
  revision = ndb.LocalStructuredProperty(RevisionRange)
  bug = ndb.LocalStructuredProperty(BugInfo)
  bisection_ids = ndb.StringProperty(repeated=True)
  anomalies = ndb.KeyProperty(repeated=True)

  @classmethod
  def GenerateAllGroupsForAnomaly(cls, anomaly_entity):
    # TODO(fancl): Support multiple group name
    return [cls(
        name=anomaly_entity.benchmark_name,
        status=cls.Status.untriaged,
        active=True,
        revision=RevisionRange(
            repository='chromium',
            start=anomaly_entity.start_revision,
            end=anomaly_entity.end_revision,
        ),
    )]

  @classmethod
  def GetGroupsForAnomaly(cls, anomaly_entity):
    # TODO(fancl): Support multiple group name
    name = anomaly_entity.benchmark_name
    revision = RevisionRange(
        repository='chromium',
        start=anomaly_entity.start_revision,
        end=anomaly_entity.end_revision,
    )
    groups = cls.Get(name, revision) or cls.Get('Ungrouped', None)
    return [g.key for g in groups]

  @classmethod
  def Get(cls, group_name, revision_info, active=True):
    query = cls.query(
        cls.active == active,
        cls.name == group_name,
    )
    if not revision_info:
      return list(query.fetch())
    return [group for group in query.fetch()
            if revision_info.IsOverlapping(group.revision)]

  @classmethod
  def GetAll(cls, active=True):
    return list(cls.query(cls.active == active).fetch())

  def Update(self):
    anomalies = anomaly.Anomaly.query(anomaly.Anomaly.groups.IN([self.key]))
    self.anomalies = [a.key for a in anomalies.fetch()]
    # TODO(fancl): Fetch issue status

  def TryTriage(self):
    # TODO(fancl): File issue
    pass

  def TryBisect(self):
    # TODO(fancl): Trigger bisection
    pass

  def Archive(self):
    self.active = False
