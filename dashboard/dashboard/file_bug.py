# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides the web interface for filing a bug on the issue tracker."""

import json
import logging

from google.appengine.api import app_identity
from google.appengine.api import urlfetch
from google.appengine.api import users
from google.appengine.ext import ndb

from dashboard import auto_bisect
from dashboard import issue_tracker_service
from dashboard import oauth2_decorator
from dashboard import request_handler
from dashboard import utils
from dashboard.models import alert
from dashboard.models import bug_data
from dashboard.models import bug_label_patterns

# A list of bug labels to suggest for all performance regression bugs.
_DEFAULT_LABELS = [
    'Type-Bug-Regression',
    'Pri-2',
]
_OMAHA_PROXY_URL = 'https://omahaproxy.appspot.com/all.json'


class FileBugHandler(request_handler.RequestHandler):
  """Uses oauth2 to file a new bug with a set of alerts."""

  def post(self):
    """A POST request for this endpoint is the same as a GET request."""
    self.get()

  @oauth2_decorator.DECORATOR.oauth_required
  def get(self):
    """Either shows the form to file a bug, or if filled in, files the bug.

    The form to file a bug is popped up from the triage-dialog polymer element.
    The default summary, description and label strings are constructed there.

    Request parameters:
      summary: Bug summary string.
      description: Bug full description string.
      owner: Bug owner email address.
      keys: Comma-separated Alert keys in urlsafe format.

    Outputs:
      HTML, using the template 'bug_result.html'.
    """
    if not utils.IsValidSheriffUser():
      # TODO(qyearsley): Simplify this message (after a couple months).
      self.RenderHtml('bug_result.html', {
          'error': ('You must be logged in with a chromium.org account '
                    'in order to file bugs here! This is the case ever '
                    'since we switched to the Monorail issue tracker. '
                    'Note, viewing internal data should work for Googlers '
                    'that are logged in with the Chromium accounts. See '
                    'https://github.com/catapult-project/catapult/issues/2042')
      })
      return

    summary = self.request.get('summary')
    description = self.request.get('description')
    labels = self.request.get_all('label')
    components = self.request.get_all('component')
    keys = self.request.get('keys')
    if not keys:
      self.RenderHtml('bug_result.html', {
          'error': 'No alerts specified to add bugs to.'
      })
      return

    if self.request.get('finish'):
      self._CreateBug(summary, description, labels, components, keys)
    else:
      self._ShowBugDialog(summary, description, keys)

  def _ShowBugDialog(self, summary, description, urlsafe_keys):
    """Sends a HTML page with a form for filing the bug.

    Args:
      summary: The default bug summary string.
      description: The default bug description string.
      urlsafe_keys: Comma-separated Alert keys in urlsafe format.
    """
    alert_keys = [ndb.Key(urlsafe=k) for k in urlsafe_keys.split(',')]
    labels, components = _FetchLabelsAndComponents(alert_keys)
    self.RenderHtml('bug_result.html', {
        'bug_create_form': True,
        'keys': urlsafe_keys,
        'summary': summary,
        'description': description,
        'labels': labels,
        'components': components,
        'owner': users.get_current_user(),
    })

  def _CreateBug(self, summary, description, labels, components, urlsafe_keys):
    """Creates a bug, associates it with the alerts, sends a HTML response.

    Args:
      summary: The new bug summary string.
      description: The new bug description string.
      labels: List of label strings for the new bug.
      components: List of component strings for the new bug.
      urlsafe_keys: Comma-separated alert keys in urlsafe format.
    """
    alert_keys = [ndb.Key(urlsafe=k) for k in urlsafe_keys.split(',')]
    alerts = ndb.get_multi(alert_keys)

    if not description:
      description = 'See the link to graphs below.'

    milestone_label = _MilestoneLabel(alerts)
    if milestone_label:
      labels.append(milestone_label)

    # Only project members (@chromium.org accounts) can be owners of bugs.
    owner = self.request.get('owner')
    if owner and not owner.endswith('@chromium.org'):
      self.RenderHtml('bug_result.html', {
          'error': 'Owner email address must end with @chromium.org.'
      })
      return

    http = oauth2_decorator.DECORATOR.http()
    service = issue_tracker_service.IssueTrackerService(http)

    bug_id = service.NewBug(
        summary, description, labels=labels, components=components, owner=owner)
    if not bug_id:
      self.RenderHtml('bug_result.html', {'error': 'Error creating bug!'})
      return

    bug_data.Bug(id=bug_id).put()
    for alert_entity in alerts:
      alert_entity.bug_id = bug_id
    ndb.put_multi(alerts)

    comment_body = _AdditionalDetails(bug_id, alerts)
    service.AddBugComment(bug_id, comment_body)

    template_params = {'bug_id': bug_id}
    if all(k.kind() == 'Anomaly' for k in alert_keys):
      bisect_result = auto_bisect.StartNewBisectForBug(bug_id)
      if 'error' in bisect_result:
        template_params['bisect_error'] = bisect_result['error']
      else:
        template_params.update(bisect_result)
    self.RenderHtml('bug_result.html', template_params)


def _AdditionalDetails(bug_id, alerts):
  """Returns a message with additional information to add to a bug."""
  base_url = '%s/group_report' % _GetServerURL()
  bug_page_url = '%s?bug_id=%s' % (base_url, bug_id)
  alerts_url = '%s?keys=%s' % (base_url, _UrlsafeKeys(alerts))
  comment = 'All graphs for this bug:\n  %s\n\n' % bug_page_url
  comment += 'Original alerts at time of bug-filing:\n  %s\n' % alerts_url
  bot_names = alert.GetBotNamesFromAlerts(alerts)
  if bot_names:
    comment += '\n\nBot(s) for this bug\'s original alert(s):\n\n'
    comment += '\n'.join(sorted(bot_names))
  else:
    comment += '\nCould not extract bot names from the list of alerts.'
  return comment


def _GetServerURL():
  return 'https://' + app_identity.get_default_version_hostname()


def _UrlsafeKeys(alerts):
  return ','.join(a.key.urlsafe() for a in alerts)


def _ComponentFromCrLabel(label):
  return label.replace('Cr-', '').replace('-', '>')

def _FetchLabelsAndComponents(alert_keys):
  """Fetches a list of bug labels and components for the given Alert keys."""
  labels = set(_DEFAULT_LABELS)
  components = set()
  alerts = ndb.get_multi(alert_keys)
  sheriff_keys = set(alert.sheriff for alert in alerts)
  sheriff_labels = [sheriff.labels for sheriff in ndb.get_multi(sheriff_keys)]
  tags = [item for sublist in sheriff_labels for item in sublist]
  for tag in tags:
    if tag.startswith('Cr-'):
      components.add(_ComponentFromCrLabel(tag))
    else:
      labels.add(tag)
  if any(a.internal_only for a in alerts):
    # This is a Chrome-specific behavior, and should ideally be made
    # more general (maybe there should be a list in datastore of bug
    # labels to add for internal bugs).
    labels.add('Restrict-View-Google')
  for test in {a.GetTestMetadataKey() for a in alerts}:
    labels_components = bug_label_patterns.GetBugLabelsForTest(test)
    for item in labels_components:
      if item.startswith('Cr-'):
        components.add(_ComponentFromCrLabel(item))
      else:
        labels.add(item)
  return labels, components


def _MilestoneLabel(alerts):
  """Returns a milestone label string, or None."""
  revisions = [a.start_revision for a in alerts if hasattr(a, 'start_revision')]
  if not revisions:
    return None
  start_revision = min(revisions)
  try:
    milestone = _GetMilestoneForRevision(start_revision)
  except KeyError:
    logging.error('List of versions not in the expected format')
  if not milestone:
    return None
  logging.info('Matched rev %s to milestone %s.', start_revision, milestone)
  return 'M-%d' % milestone


def _GetMilestoneForRevision(revision):
  """Finds the oldest milestone for a given revision from OmahaProxy.

  The purpose of this function is to resolve the milestone that would be blocked
  by a suspected regression. We do this by locating in the list of current
  versions, regardless of platform and channel, all the version strings (e.g.
  36.0.1234.56) that match revisions (commit positions) later than the earliest
  possible start_revision of the suspected regression; we then parse out the
  first numeric part of such strings, assume it to be the corresponding
  milestone, and return the lowest one in the set.

  Args:
    revision: An integer or string containing an integer.

  Returns:
    An integer representing the lowest milestone matching the given revision or
    the highest milestone if the given revision exceeds all defined milestones.
    Note that the default is 0 when no milestones at all are found. If the
    given revision is None, then None is returned.
  """
  if revision is None:
    return None
  milestones = set()
  default_milestone = 0
  all_versions = _GetAllCurrentVersionsFromOmahaProxy()
  for os in all_versions:
    for version in os['versions']:
      try:
        milestone = int(version['current_version'].split('.')[0])
        version_commit = version.get('branch_base_position')
        if version_commit and int(revision) < int(version_commit):
          milestones.add(milestone)
        if milestone > default_milestone:
          default_milestone = milestone
      except ValueError:
        # Sometimes 'N/A' is given. We ignore these entries.
        logging.warn('Could not cast one of: %s, %s, %s as an int',
                     revision, version['branch_base_position'],
                     version['current_version'].split('.')[0])
  if milestones:
    return min(milestones)
  return default_milestone


def _GetAllCurrentVersionsFromOmahaProxy():
  """Retrieves a the list current versions from OmahaProxy and parses it."""
  try:
    response = urlfetch.fetch(_OMAHA_PROXY_URL)
    if response.status_code == 200:
      return json.loads(response.content)
  except urlfetch.Error:
    logging.error('Error pulling list of current versions (omahaproxy).')
  except ValueError:
    logging.error('OmahaProxy did not return valid JSON.')
  return []
