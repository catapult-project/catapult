# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from application.clients import datastore_client
from application.clients import sheriff_config_client


class NoEntityFoundException(Exception):
  pass


class SheriffConfigRequestException(Exception):
  pass

class AlertGroup:
  ds_client = datastore_client.DataStoreClient()

  @classmethod
  def FindDuplicates(cls, group_id):
    '''Find the alert groups which are using the current group as canonical.

    Args:
      group_id: the id of the current group.

    Return:
      a list of groud ids.
    '''
    filters = [('canonical_group', '=', cls.ds_client.AlertGroupKey(group_id))]
    duplicates = list(cls.ds_client.QueryAlertGroup(extra_filters=filters))

    return [cls.ds_client.GetEntityId(g, key_type='name') for g in duplicates]


  @classmethod
  def FindCanonicalGroupByIssue(cls, current_group_id, issue_id, project_name):
    '''Find the canonical group which the current group's issue is merged to.

    Consider an alert group GA has a filed issue A, another group GB has filed
    issue B. If A is merged into B, then GB is consider the canonical group of
    GA.

    Args:
      current_group_id: the id of the current group
      issue_id: the id of the issue which is merged to.
      project_name: the monorail project name of the issue.

    Returns:
      The id of the canonical group.
    '''
    filters = [
      ('bug.bug_id', '=', issue_id),
      ('bug.project', '=', project_name)
    ]

    query_result = list(cls.ds_client.QueryAlertGroup(extra_filters=filters, limit=1))

    if not query_result:
      return None

    canonical_group = query_result[0]
    visited = {current_group_id}
    while dict(canonical_group).get('canonical_group'):
      visited.add(canonical_group.key.name)
      next_group_key = dict(canonical_group).get('canonical_group')
      # Visited check is just precaution.
      # If it is true - the system previously failed to prevent loop creation.
      if next_group_key.name in visited:
        logging.warning(
            'Alert group auto merge failed. Found a loop while '
            'searching for a canonical group for %r', current_group_id)
        return None
      canonical_group = cls.ds_client.GetEntityByKey(next_group_key)

    return canonical_group.key.name


  @classmethod
  def GetAnomaliesByID(cls, group_id):
    ''' Given a group id, return a list of anomaly id.

    Args:
      group_id: the id of the alert group

    Returns:
      A list of anomaly IDs.
    '''
    group_key = cls.ds_client.AlertGroupKey(group_id)
    group = cls.ds_client.GetEntityByKey(group_key)
    if group:
      return [a.id for a in group.get('anomalies')]
    raise NoEntityFoundException('No Alert Group Found with id: %s', group_id)

  @classmethod
  def Get(cls, group_name, group_type, active=True):
    ''' Get a list of alert groups by the group name and group type

    Args:
      group_name: the name value of the alert group
      group_type: the group type, which should be either 0 (test_suite)
                  or 2 (reserved)
    Returns:
      A list of ids of the matched alert groups
    '''
    filters = [
      ('name', '=', group_name)
    ]
    groups = list(cls.ds_client.QueryAlertGroup(active=active, extra_filters=filters))

    return [g for g in groups if g.get('group_type') == group_type]


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

    Args:
      test_key: the key of a test metadata
      start_rev: the start revision of the anomaly
      end_rev: the end revision of the anomaly
      create_on_ungrouped: the located subscription will have a new alert
          group created if this value is true; otherwise, the existing
          'upgrouped' group will be used.
      parity: testing flag for result parity

    Returns:
      a list of group ids.
    '''
    sc_client = sheriff_config_client.GetSheriffConfigClient()
    matched_configs, err_msg = sc_client.Match(test_key)

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
        if (g['domain'] == master_name and
            g['subscription_name'] == s.get('name') and
            g['project_id'] == s.get('monorail_project_id', '') and
            max(g['revision']['start'], start_rev) <= min(g['revision']['end'], end_rev) and
            (abs(g['revision']['start'] - start_rev) + abs(g['revision']['end'] - end_rev) <= 100 or g['domain'] != 'ChromiumPerf')):
          has_overlapped = True
          result_groups.add(g.key.name)
      if not has_overlapped:
        if create_on_ungrouped:
          new_group = cls.ds_client.NewAlertGroup(
            benchmark_name=benchmark_name,
            master_name=master_name,
            subscription_name=s.get('name'),
            group_type=datastore_client.AlertGroupType.test_suite,
            project_id=s.get('monorail_project_id', ''),
            start_rev=start_rev,
            end_rev=end_rev
          )
          logging.info('Saving new group %s', new_group.key.name)
          if parity:
            new_groups.add(new_group.key.name)
          else:
            cls.ds_client.SaveAlertGroup(new_group)
          result_groups.add(new_group.key.name)
        else:
          # return the id of the 'ungrouped'
          ungrouped = cls._GetUngroupedGroup()
          if ungrouped:
            result_groups.add(ungrouped.key.id)

    logging.debug('GetGroupsForAnomaly returning %s', result_groups)
    return list(result_groups), list(new_groups)


  @classmethod
  def GetAll(cls):
    """Fetch all active alert groups

    Returns:
      A list of active alert groups
    """
    groups = list(cls.ds_client.QueryAlertGroup())

    return [cls.ds_client.GetEntityId(g) for g in groups]


  @classmethod
  def _GetUngroupedGroup(cls):
    ''' Get the "ungrouped" group

    The alert_group named "ungrouped" contains the alerts for further
    processing in the next iteration of of dashboard-alert-groups-update
    cron job.

    Returns:
      The 'ungrouped' entity if exists, otherwise create a new entity and
      return None.
    '''
    ungrouped_groups = cls.Get('Ungrouped', 2)
    if not ungrouped_groups:
      # initiate when there is no active group called 'Ungrouped'.
      new_group = cls.ds_client.NewAlertGroup(
        benchmark_name='Ungrouped',
        group_type=0
      )
      cls.ds_client.SaveAlertGroup(new_group)
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

    with cls.ds_client.Transaction():
      ungrouped_anomalies = cls.ds_client.get_multi(ungrouped.anomalies)
      logging.info('Loaded %s ungrouped alerts from "ungrouped". ID(%s)',
                    len(ungrouped_anomalies), ungrouped.key.id)

      parity_results = {}
      for anomaly in ungrouped_anomalies:
        group_ids, new_ids = cls.GetGroupsForAnomaly(
          anomaly['test'].name, anomaly['start_revision'], anomaly['end_revision'],
          create_on_ungrouped=True, parity=IS_PARITY)
        anomaly['groups'] = [cls.ds_client.AlertGroupKey(group_id) for group_id in group_ids]
        if IS_PARITY:
          anomaly_id = anomaly.key.id
          parity_results[anomaly_id] = {
            "existing_groups": list(set(group_ids) - set(new_ids)),
            "new_groups": new_ids
          }
        else:
          cls.ds_client.SaveAnomaly(anomaly)

    return parity_results
