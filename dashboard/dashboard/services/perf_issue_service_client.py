# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# adding even we are running in python 3 to avoid pylint 2.7 complains.
from __future__ import absolute_import

import logging

from dashboard.common import cloud_metric
from dashboard.common import utils
from dashboard.services import request

STATUS_DUPLICATE = 'Duplicate'

if utils.IsStagingEnvironment():
  _SERVICE_URL = 'https://perf-issue-service-dot-chromeperf-stage.uc.r.appspot.com/'
else:
  _SERVICE_URL = 'https://perf-issue-service-dot-chromeperf.appspot.com/'

_ISSUES_PERFIX = 'issues/'


def GetIssues(**kwargs):
  url = _SERVICE_URL + _ISSUES_PERFIX
  try:
    resp = request.RequestJson(url, method='GET', **kwargs)
    return resp
  except request.RequestError as e:
    cloud_metric.PublishPerfIssueServiceRequestFailures('GetIssues', 'GET', url,
                                                        kwargs)
    logging.error('[PerfIssueService] Error requesting issue list (%s): %s',
                  kwargs, str(e))
    return []


def GetIssue(issue_id, project_name='chromium'):
  url = _SERVICE_URL + _ISSUES_PERFIX
  url += '%s/project/%s' % (issue_id, project_name)
  try:
    resp = request.RequestJson(url, method='GET')
    return resp
  except request.RequestError as e:
    cloud_metric.PublishPerfIssueServiceRequestFailures(
        'GetIssue', 'GET', url, {
            'issue_id': issue_id,
            'project_name': project_name
        })
    logging.error(
        '[PerfIssueService] Error requesting issue (id: %s, project: %s): %s',
        issue_id, project_name, str(e))
    return None


def GetIssueComments(issue_id, project_name='chromium'):
  url = _SERVICE_URL + _ISSUES_PERFIX
  url += '%s/project/%s/comments' % (issue_id, project_name)
  try:
    resp = request.RequestJson(url, method='GET')
    return resp
  except request.RequestError as e:
    cloud_metric.PublishPerfIssueServiceRequestFailures(
        'GetIssueComments', 'GET', url, {
            'issue_id': issue_id,
            'project_name': project_name
        })
    logging.error(
        '[PerfIssueService] Error requesting comments (id: %s, project: %s): %s',
        issue_id, project_name, str(e))
    return []


def PostIssue(**kwargs):
  url = _SERVICE_URL + _ISSUES_PERFIX
  try:
    resp = request.RequestJson(url, method='POST', body=kwargs)
    return resp
  except request.RequestError as e:
    cloud_metric.PublishPerfIssueServiceRequestFailures('PostIssue', 'POST',
                                                        url, kwargs)
    logging.error('[PerfIssueService] Error requesting new issue (%s): %s',
                  kwargs, str(e))
    return []


def PostIssueComment(issue_id, project_name='chromium', **kwargs):
  url = _SERVICE_URL + _ISSUES_PERFIX
  url += '%s/project/%s/comments' % (issue_id, project_name)
  try:
    resp = request.RequestJson(url, method='POST', body=kwargs)
    return resp
  except request.RequestError as e:
    cloud_metric.PublishPerfIssueServiceRequestFailures('PostIssueComment',
                                                        'POST', url, kwargs)
    logging.error(
        '[PerfIssueService] Error requesting new issue comment (id: %s, project: %s data: %s): %s',
        issue_id, project_name, kwargs, str(e))
    return []
