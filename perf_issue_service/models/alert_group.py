# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.cloud import ndb


class NoEntityFoundException(Exception):
  pass

class RevisionRange(ndb.Model):
  repository = ndb.StringProperty()
  start = ndb.IntegerProperty()
  end = ndb.IntegerProperty()

class AlertGroup(ndb.Model):
  name = ndb.StringProperty(indexed=True)
  domain = ndb.StringProperty(indexed=True)
  subscription_name = ndb.StringProperty(indexed=True)
  created = ndb.DateTimeProperty(indexed=False, auto_now_add=True)
  updated = ndb.DateTimeProperty(indexed=False, auto_now_add=True)

  class Status:
    unknown = 0
    untriaged = 1
    triaged = 2
    bisected = 3
    closed = 4

  status = ndb.IntegerProperty(indexed=False)

  class Type:
    test_suite = 0
    logical = 1
    reserved = 2

  group_type = ndb.IntegerProperty(
      indexed=False,
      choices=[Type.test_suite, Type.logical, Type.reserved],
      default=Type.test_suite,
  )
  active = ndb.BooleanProperty(indexed=True)
  revision = ndb.LocalStructuredProperty(RevisionRange)
#   bug = ndb.StructuredProperty(BugInfo, indexed=True)
  project_id = ndb.StringProperty(indexed=True, default='chromium')
  bisection_ids = ndb.StringProperty(repeated=True)
  anomalies = ndb.KeyProperty(repeated=True)
  # Key of canonical AlertGroup. If not None the group is considered to be
  # duplicate.
  canonical_group = ndb.KeyProperty(indexed=True)

  @classmethod
  def GetAnomaliesByID(cls, group_id):
    """ Given a group id, return a list of anomaly id.
    """
    client = ndb.Client()
    with client.context():
      group = ndb.Key('AlertGroup', group_id).get()
      if group:
        return [a.integer_id() for a in group.anomalies]
      raise NoEntityFoundException('No Alert Group Found with id: %s', group_id)

  @classmethod
  def Get(cls, group_name, group_type, active=True):
    client = ndb.Client()
    with client.context():
      query = cls.query(
          cls.active == active,
          cls.name == group_name,
      )
      return [g for g in query.fetch() if g.group_type == group_type]


  @classmethod
  def GetGroupsForAnomaly(cls, test_key, start_rev, end_rev, subscription_names, project_names):
    logging.debug('GetGroupsForAnomaly(%s, %s, %s, %s, %s)', test_key, start_rev, end_rev, subscription_names, project_names)
    subscriptions = subscription_names.split(',')
    projects = [p if p != 'null' else '' for p in project_names.split(',')]
    start_rev = int(start_rev)
    end_rev = int(end_rev)
    if len(subscriptions) != len(projects):
      logging.warning('Length mismatch on subcriptions: %s %s', subscriptions, projects)
      return []
    subs_info = list(zip(subscriptions, projects))
    master_name = test_key.split('/')[0]
    benchmark_name = test_key.split('/')[2]

    existing_groups = cls.Get(benchmark_name, 0)
    result_groups = set()
    for sub in subs_info:
      # for each matched subscription, try to find the overlapped existing
      # groups
      has_overlapped = False
      for g in existing_groups:
        if g.domain == master_name and g.subscription_name == sub[0] and g.project_id == sub[1] and max(g.revision.start, start_rev) <= min(g.revision.end, end_rev) and abs(g.revision.start - start_rev) + abs(g.revision.end - end_rev) <= 100:
          has_overlapped = True
          result_groups.add(g.key.string_id())
      if not has_overlapped:
        result_groups.add('ungrouped')

    logging.debug('GetGroupsForAnomaly returning %s', result_groups)
    return list(result_groups)
