# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import uuid

from google.cloud import ndb

from models import anomaly
from application.clients import sheriff_config_client


class NoEntityFoundException(Exception):
  pass


class SheriffConfigRequestException(Exception):
  pass


class RevisionRange(ndb.Model):
  repository = ndb.StringProperty()
  start = ndb.IntegerProperty()
  end = ndb.IntegerProperty()

class BugInfo(ndb.Model):
  project = ndb.StringProperty(indexed=True)
  bug_id = ndb.IntegerProperty(indexed=True)

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
  bug = ndb.StructuredProperty(BugInfo, indexed=True)
  project_id = ndb.StringProperty(indexed=True, default='chromium')
  bisection_ids = ndb.StringProperty(repeated=True)
  anomalies = ndb.KeyProperty(repeated=True)
  # Key of canonical AlertGroup. If not None the group is considered to be
  # duplicate.
  canonical_group = ndb.KeyProperty(indexed=True)

  @classmethod
  def FindDuplicates(cls, group_id):
    client = ndb.Client()
    with client.context():
      query = cls.query(
          cls.active == True,
          cls.canonical_group == ndb.Key('AlertGroup', group_id))
      duplicates = query.fetch()
      return [g.key.string_id() for g in duplicates]


  @classmethod
  def FindCanonicalGroupByIssue(cls, current_group_key, issue_id, project_name):
    client = ndb.Client()
    with client.context():
      query = cls.query(
          cls.active == True,
          cls.bug.project == project_name,
          cls.bug.bug_id == issue_id)
      query_result = query.fetch(limit=1)
      if not query_result:
        return None

      canonical_group = query_result[0]
      visited = set()
      while canonical_group.canonical_group:
        visited.add(canonical_group.key)
        next_group_key = canonical_group.canonical_group
        # Visited check is just precaution.
        # If it is true - the system previously failed to prevent loop creation.
        if next_group_key == current_group_key or next_group_key in visited:
          logging.warning(
              'Alert group auto merge failed. Found a loop while '
              'searching for a canonical group for %r', current_group_key)
          return None
        canonical_group = next_group_key.get()

      return canonical_group.key.string_id()


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
  def GetGroupsForAnomaly(
    cls, test_key, start_rev, end_rev, create_on_ungrouped=False, parity=False):
    ''' Find the alert groups for the anomaly.

    Given the test_key and revision range of an anomaly:
    1. find the subscriptions.
    2. for each subscriptions, find the groups for the anomaly.
        if no existing group is found:
         - if create_on_ungrouped is True, create a new group.
         - otherwise, use the 'ungrouped'.
    '''
    client = sheriff_config_client.GetSheriffConfigClient()
    matched_configs, err_msg = client.Match(test_key)

    if err_msg is not None:
      raise SheriffConfigRequestException(err_msg)

    if not matched_configs:
      return []

    start_rev = int(start_rev)
    end_rev = int(end_rev)
    master_name = test_key.split('/')[0]
    benchmark_name = test_key.split('/')[2]

    existing_groups = cls.Get(benchmark_name, 0)
    result_groups = set()
    new_groups = set()
    for config in matched_configs:
      s = config['subscription']
      has_overlapped = False
      for g in existing_groups:
        if (g.domain == master_name and
            g.subscription_name == s.get('name') and
            g.project_id == s.get('monorail_project_id', '') and
            max(g.revision.start, start_rev) <= min(g.revision.end, end_rev) and
            (abs(g.revision.start - start_rev) + abs(g.revision.end - end_rev) <= 100 or g.domain != 'ChromiumPerf')):
          has_overlapped = True
          result_groups.add(g.key.string_id())
      if not has_overlapped:
        if create_on_ungrouped:
          client = ndb.Client()
          with client.context():
            new_id = str(uuid.uuid4())
            new_group = cls(
              id=new_id,
              name=benchmark_name,
              domain=master_name,
              subscription_name=s.get('name'),
              project_id=s.get('monorail_project_id', ''),
              status=cls.Status.untriaged,
              group_type=cls.Type.test_suite,
              active=True,
              revision=RevisionRange(
                repository='chromium',
                start=start_rev,
                end=end_rev
              )
            )
            logging.info('Saving new group %s', new_id)
            if parity:
              new_groups.add(new_id)
            new_group.put()
          result_groups.add(new_id)
        else:
          # return the id of the 'ungrouped'
          ungrouped = cls._GetUngroupedGroup()
          result_groups.add(ungrouped.key.integer_id())

    logging.debug('GetGroupsForAnomaly returning %s', result_groups)
    return list(result_groups), list(new_groups)


  @classmethod
  def GetAll(cls):
    client = ndb.Client()
    with client.context():
      groups = cls.query(cls.active == True).fetch()
      return [g.key.id() for g in groups]


  @classmethod
  def _GetUngroupedGroup(cls):
    ''' Get the "ungrouped" group

    The alert_group named "ungrouped" contains the alerts for further
    processing in the next iteration of of dashboard-alert-groups-update
    cron job.
    '''
    ungrouped_groups = cls.Get('Ungrouped', 2)
    client = ndb.Client()
    with client.context():
      if not ungrouped_groups:
        # initiate when there is no active group called 'Ungrouped'.
        cls(name='Ungrouped', group_type=cls.Type.reserved, active=True).put()
        return None
      if len(ungrouped_groups) != 1:
        logging.warning('More than one active groups are named "Ungrouped".')
      ungrouped = ungrouped_groups[0]
      return ungrouped


  @classmethod
  def ProcessUngroupedAlerts(cls):
    """ Process each of the alert which needs a new group

    This alerts are added to the 'ungrouped' group during anomaly detection
    when no existing group is found to add them to.
    """
    IS_PARITY = True
    ungrouped = cls._GetUngroupedGroup()
    if not ungrouped:
      return
    client = ndb.Client()
    with client.context():
      ungrouped_anomalies = ndb.get_multi(ungrouped.anomalies)
      logging.info('Loaded %s ungrouped alerts from "ungrouped". ID(%s)',
                  len(ungrouped_anomalies), ungrouped.key.integer_id())

    parity_results = {}
    for anomaly in ungrouped_anomalies:
      group_ids, new_ids = cls.GetGroupsForAnomaly(
        anomaly.test.id(), anomaly.start_revision, anomaly.end_revision,
        create_on_ungrouped=True, parity=IS_PARITY)
      with client.context():
        anomaly.groups = [ndb.Key('AlertGroup', group_id) for group_id in group_ids]
        if IS_PARITY:
          anomaly_id = anomaly.key.integer_id()
          parity_results[anomaly_id] = {
            "existing_groups": list(set(group_ids) - set(new_ids)),
            "new_groups": new_ids
          }
        anomaly.put()

    return parity_results
