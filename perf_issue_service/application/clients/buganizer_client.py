# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Provides a layer of abstraction for the buganizer API."""

from http import client as http_client
import json
import logging

from apiclient import discovery
from apiclient import errors
from application import utils
from application import buganizer_utils as b_utils


_DISCOVERY_URI = ('https://issuetracker.googleapis.com/$discovery/rest?version=v1&labels=GOOGLE_PUBLIC')

BUGANIZER_SCOPES = 'https://www.googleapis.com/auth/buganizer'
MAX_DISCOVERY_RETRIES = 3
MAX_REQUEST_RETRIES = 5


class NoComponentException(Exception):
  pass


class BuganizerClient:
  """Class for updating perf issues."""

  def __init__(self):
    """Initializes an object for communicate to the Buganizer.
    """
    http = utils.ServiceAccountHttp(BUGANIZER_SCOPES)
    http.timeout = 30

    # Retry connecting at least 3 times.
    attempt = 1
    while attempt != MAX_DISCOVERY_RETRIES:
      try:
        self._service = discovery.build(
            'issuetracker', 'v1', discoveryServiceUrl=_DISCOVERY_URI, http=http)
        break
      except http_client.HTTPException as e:
        logging.error('Attempt #%d: %s', attempt, e)
        if attempt == MAX_DISCOVERY_RETRIES:
          raise
      attempt += 1


  def GetIssuesList(self, limit, age, status, labels, project='chromium'):
    """Makes a request to the issue tracker to list issues.

    Args:
      limit: the limit of results to fetch
      age: the number of days after the issue was created
      status: the status of the issues
      labels: the labels (hotlists) of the issue.
              The term 'labels' is what we use in Monorail and it is no longer
              available in Buganizer. Instead, we will use hotlists.
      project: the project name in Monorail. It is not needed in Buganizer. We
              will use it to look for the corresponding 'component'.

    Returns:
      a list of issues.
      (The issues are now in Monorail format before consumers are updated.)
    """
    project = 'chromium' if project is None or not project.strip() else project

    components = b_utils.FindBuganizerComponents(monorail_project_name=project)
    if not components:
      logging.warning(
        '[Buganizer API] Failed to find components for the given project: %s',
        project)
      return []
    components_string = '|'.join(components)
    query_string = 'componentid:%s' % components_string

    # by default, buganizer return all.
    if status and status != 'all':
      query_string += ' AND status:%s' % status

    if age:
      query_string += ' AND created:%sd' % age

    if labels:
      label_list = labels.split(',')
      hotlists = b_utils.FindBuganizerHotlists(label_list)
      if hotlists:
        query_string += ' AND hotlistid:%s' % '|'.join(hotlists)

    logging.info('[PerfIssueService] GetIssueList Query: %s', query_string)
    request = self._service.issues().list(
      query=query_string,
      pageSize=min(500, int(limit)),
      view='FULL'
    )
    response = self._ExecuteRequest(request)

    buganizer_issues = response.get('issues', []) if response else []

    logging.debug('Buganizer Issues: %s', buganizer_issues)

    monorail_issues = [
      b_utils.ReconcileBuganizerIssue(issue) for issue in buganizer_issues]

    return monorail_issues


  def GetIssue(self, issue_id, project='chromium'):
    """Makes a request to the issue tracker to get an issue.

    Args:
      issue_id: the id of the issue

    Returns:
      an issue.
      (The issues are now in Monorail format before consumers are updated.)
    """
    del project
    request = self._service.issues().get(issueId=issue_id, view='FULL')
    buganizer_issue = self._ExecuteRequest(request)

    logging.debug('Buganizer Comments for %s: %s', issue_id, buganizer_issue)

    monorail_issue = b_utils.ReconcileBuganizerIssue(buganizer_issue)

    return monorail_issue


  def GetIssueComments(self, issue_id, project='chromium'):
    """Gets all the comments for the given issue.

    The GetIssueComments is used only in the alert group workflow to check
    whether the issue is closed by Pinpoint (chromeperf's service account).
    Unlike Monorail, status update and comments are two independent workflows
    in Buganizer. As the existing workflow only looks for the status update,
    we will get the issue updates instead of issue comments.
    To avoid changes on client side, I keep the field name in 'comments' in
    the return value.

    Args:
      issue_id: the id of the issue.

    Returns:
      a list of updates of the issue.
    (The updates are now in Monorail format before consumers are updated.)
    """
    del project

    request = self._service.issues().issueUpdates().list(issueId=issue_id)
    response = self._ExecuteRequest(request)

    logging.debug('Buganizer Issue for %s: %s', issue_id, response)

    schema = self._service._schema.get('IssueState')
    status_enum = schema['properties']['status']['enum']

    if not response:
      return []

    return [{
        'id': update.get('version'),
        'author': update.get('author', {}).get('emailAddress', ''),
        'content': update.get('issueComment', {}).get('comment', ''),
        'published': update.get('timestamp'),
        'updates': b_utils.GetBuganizerStatusUpdate(update, status_enum) or {}
    } for update in response.get('issueUpdates')]


  def NewIssue(self,
             title,
             description,
             project='chromium',
             labels=None,
             components=None,
             owner=None,
             cc=None,
             status=None):
    ''' Create an issue on Buganizer

    While the API looks the same as in monorail_client, similar to what we do
    in reconciling buganizer data, we need to reconstruct the data in the
    reversed way: from the monorail fashion to the buganizer fashion.
    The issueState property should always exist for an Issue, and these
    properties are required for an issueState:
      title, componentId, status, type, severity, priority.

    Args:
      title: a string as the issue title.
      description: a string as the initial description of the issue.
      project: this is no longer needed in Buganizer. When creating an issue,
          we will NOT use it to look for the corresponding components.
      labels: a list of Monorail labels, each of which will be mapped to a
          Buganizer hotlist id.
      components: a list of component names in Monorail. The size of the list
          should always be 1 as required by Buganizer.
      owner: the email address of the issue owner/assignee.
      cc: a list of email address to which the issue update is cc'ed.
      status: the initial status of the issue

    Returns:
      {'issue_id': id, 'project_id': project_name} if succeeded; otherwise
      {'error': error_msg}
    '''
    if not components:
      raise NoComponentException(
        'Componenet ID is required when creating a new issue on Buganizer.')
    if len(components)>1:
      logging.warning(
        '[PerfIssueService] More than 1 components on issue create. Using the first one.')
    buganizer_component_id = b_utils.FindBuganizerComponentId(components[0])

    if owner:
      monorail_status = 'Assigned'
    elif not status:
      monorail_status = 'Unconfirmed'
    else:
      monorail_status = status
    buganizer_status = b_utils.FindBuganizerStatus(monorail_status)

    priority  = 'P%s' % b_utils.LoadPriorityFromMonorailLabels(labels)
    labels = [label for label in labels if not label.startswith('Pri-')]

    new_issue_state = {
      'title': title,
      'componentId': buganizer_component_id,
      'status': buganizer_status,
      'type': 'BUG',
      'severity': 'S2',
      'priority': priority,
    }

    new_description = {
      'comment': description
    }

    if owner:
      new_issue_state['assignee'] = {
        'emailAddress': owner
      }
    if cc:
      emails = set(email.strip() for email in cc if email.strip())
      new_issue_state['ccs'] = [
        {'emailAddress': email} for email in emails if email
      ]
    if labels:
      hotlist_list = b_utils.FindBuganizerHotlists(labels)
      new_issue_state['hotlistIds'] = [hotlist for hotlist in hotlist_list]

    new_issue = {
      'issueState': new_issue_state,
      'issueComment': new_description
    }

    logging.warning('[PerfIssueService] PostIssue request: %s', new_issue)
    request = self._service.issues().create(body=new_issue)

    try:
      response = self._ExecuteRequest(request)
      logging.debug('[PerfIssueService] PostIssue response: %s', response)
      if response and 'issueId' in response:
        return {'issue_id': response['issueId'], 'project_id': project}
      logging.error('Failed to create new issue; response %s', response)
    except errors.HttpError as e:
      reason = self._GetErrorReason(e)
      return {'error': reason}
    except http_client.HTTPException as e:
      return {'error': str(e)}
    return {'error': 'Unknown failure creating issue.'}


  def NewComment(self,
                  issue_id,
                  project='chromium',
                  comment='',
                  title=None,
                  status=None,
                  merge_issue=None,
                  owner=None,
                  cc=None,
                  components=None,
                  labels=None,
                  send_email=True):
    ''' Add a new comment for an existing issue
    '''
    # TODO: need to handle the merge_issue and send_email.

    if not issue_id or issue_id < 0:
      return {
        'error': '[PerfIssueService] Missing issue id on PostIssueComment'
        }

    add_issue_state, remove_issue_state = {}, {}

    if title:
      add_issue_state['title'] = title

    if status:
      add_issue_state['status'] = b_utils.FindBuganizerStatus(status)

    if owner:
      add_issue_state['assignee'] = {'emailAddress': owner}

    if components:
      if len(components)>1:
        logging.warning(
          '[PerfIssueService] More than 1 components on issue create. Using the first one.')
      add_issue_state['componentId'] = b_utils.FindBuganizerComponentId(components[0])

    if labels and any(label.startswith('Pri-') for label in labels):
      priority  = 'P%s' % b_utils.LoadPriorityFromMonorailLabels(labels)
      add_issue_state['priority'] = priority
      labels = [label for label in labels if not label.startswith('Pri-')]

    hotlist_ids = b_utils.FindBuganizerHotlists(labels)
    if cc or hotlist_ids:
      request = self._service.issues().get(issueId=str(issue_id), view='FULL')
      current_state = self._ExecuteRequest(request)
      if cc:
        current_cc = [cc['emailAddress'] for cc in current_state['issueState'].get('ccs', [])]
        to_add_cc = list(set(cc) - set(current_cc))
        if to_add_cc:
          add_issue_state['ccs'] = [
            {'emailAddress': cc} for cc in to_add_cc if cc
          ]
        to_remove_cc = list(set(current_cc) - set(cc))
        if to_remove_cc:
          remove_issue_state['ccs'] = [
            {'emailAddress': cc} for cc in to_remove_cc if cc
          ]
      if hotlist_ids:
        current_hotlists = current_state['issueState'].get('hotlistIds', [])

        to_add_hotlists = list(set(hotlist_ids) - set(current_hotlists))
        for hotlist_id in to_add_hotlists:
          hotlist_entry_request = {'hotlistEntry': {'issueId': issue_id}}
          request = self._service.hotlists().createEntries(
            hotlistId=hotlist_id, body=hotlist_entry_request)
          response = self._ExecuteRequest(request)
          logging.debug('[PerfIssueService] Add hotlist response: %s', response)
        to_remove_hotlists = list(set(current_hotlists) - set(hotlist_ids))
        for hotlist_id in to_remove_hotlists:
          request = self._service.hotlists().entries().delete(
            hotlistId=str(hotlist_id), issueId=str(issue_id))
          response = self._ExecuteRequest(request)
          logging.debug('[PerfIssueService] Delete hotlist response: %s', response)

    modify_request = {}
    if comment:
      modify_request['issueComment'] = {'comment': comment}
    if add_issue_state:
      modify_request['addMask'] = ','.join(add_issue_state.keys())
      modify_request['add'] = add_issue_state
    if remove_issue_state:
      modify_request['removeMask'] = ','.join(remove_issue_state.keys())
      modify_request['remove'] = remove_issue_state

    if not modify_request:
      return {}

    response = self._MakeCommentRequest(issue_id, modify_request)

    return response


  def _MakeCommentRequest(self, issue_id, modify_request, retry=True):
    try:
      logging.debug('[PerfIssueService] Post comment request body %s', modify_request)
      request = self._service.issues().modify(issueId=str(issue_id), body=modify_request)
      response = self._ExecuteRequest(request)
      logging.debug('[PerfIssueService] Post comment response %s', response)
      if response:
        return response
    except errors.HttpError as e:
      logging.error(
        '[PerfIssueService] Buganizer error on post comments: %s', str(e))
      reason = self._GetErrorReason(e)
      if reason is None:
        reason = ''
      if retry and 'The user does not exist' in reason:
        if 'assignee' in modify_request.get('addMask', ''):
          current_add_mask_list = modify_request.get('addMask').split(',')
          current_add_mask_list.remove('assignee')
          new_add_mask = ','.join(current_add_mask_list)
          modify_request['addMask'] = new_add_mask
          del modify_request['add']['assignee']
        if 'ccs' in modify_request.get('addMask', ''):
          current_add_mask_list = modify_request.get('addMask').split(',')
          current_add_mask_list.remove('ccs')
          new_add_mask = ','.join(current_add_mask_list)
          modify_request['ccs'] = new_add_mask
          del modify_request['add']['ccs']
        return self._MakeCommentRequest(issue_id, modify_request, retry=False)

    err_msg = 'Error updating issue %s with body %s' % (
      issue_id, modify_request)
    logging.error(err_msg)
    return {'error': err_msg}


  def _ExecuteRequest(self, request):
    """Makes a request to the issue tracker.

    Args:
      request: The request object, which has a execute method.

    Returns:
      The response if there was one, or else None.
    """
    response = request.execute(
        num_retries=MAX_REQUEST_RETRIES,
        http=utils.ServiceAccountHttp(BUGANIZER_SCOPES))
    return response


  def _GetErrorReason(self, request_error):
    if request_error.resp.get('content-type', '').startswith('application/json'):
      error_json = json.loads(request_error.content).get('error')
      if error_json:
        return error_json.get('message')
    return None
