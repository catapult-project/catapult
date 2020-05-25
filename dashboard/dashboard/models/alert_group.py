# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""The database model for an "Anomaly", which represents a step up or down."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import uuid

from google.appengine.ext import ndb

# Move import of protobuf-dependent code here so that all AppEngine work-arounds
# have a chance to be live before we import any proto code.
from dashboard import sheriff_config_client


class RevisionRange(ndb.Model):
  repository = ndb.StringProperty()
  start = ndb.IntegerProperty()
  end = ndb.IntegerProperty()

  def IsOverlapping(self, b):
    if not b or self.repository != b.repository:
      return False
    return max(self.start, b.start) <= min(self.end, b.end)


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
  project_id = ndb.StringProperty(indexed=True, default='chromium')
  bisection_ids = ndb.StringProperty(repeated=True)
  anomalies = ndb.KeyProperty(repeated=True)

  def IsOverlapping(self, b):
    return (self.name == b.name and self.project_id == b.project_id and
            self.revision.IsOverlapping(b.revision))

  @classmethod
  def GenerateAllGroupsForAnomaly(cls, anomaly_entity, sheriff_config=None):
    sheriff_config = (
        sheriff_config or sheriff_config_client.GetSheriffConfigClient())
    subscriptions, _ = sheriff_config.Match(
        anomaly_entity.test.string_id(), check=True)

    # We want to create an issue per project if multiple subscriptions apply to
    # this anomaly that have different projects.
    projects = set(s.monorail_project_id for s in subscriptions)
    return [
        # TODO(fancl): Support multiple group name
        cls(
            id=str(uuid.uuid4()),
            name=anomaly_entity.benchmark_name,
            project_id=project,
            status=cls.Status.untriaged,
            active=True,
            revision=RevisionRange(
                repository='chromium',
                start=anomaly_entity.start_revision,
                end=anomaly_entity.end_revision,
            ),
        ) for project in projects
    ]

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
  def GetByID(cls, group_id):
    return ndb.Key('AlertGroup', group_id).get()

  @classmethod
  def Get(cls, group_name, revision_info, active=True):
    query = cls.query(
        cls.active == active,
        cls.name == group_name,
    )
    if not revision_info:
      return list(query.fetch())
    return [
        group for group in query.fetch()
        if revision_info.IsOverlapping(group.revision)
    ]

  @classmethod
  def GetAll(cls, active=True):
    groups = cls.query(cls.active == active).fetch()
    return groups or []
