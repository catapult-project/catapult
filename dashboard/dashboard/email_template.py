# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Defines common functionality used for generating e-mail to sheriffs."""

import logging
import re
import urllib

from google.appengine.api import urlfetch

from dashboard import utils
from dashboard.models import bug_label_patterns

_SINGLE_EMAIL_SUBJECT = (
    '%(percent_changed)s %(change_type)s in %(test_name)s '
    'on %(bot)s at %(start)d:%(end)d')

_EMAIL_HTML_TABLE = """
A <b>%(percent_changed)s</b> %(change_type)s.<br>
<table cellpadding='4'>
  <tr><td>Master:</td><td><b>%(master)s</b></td>
  <tr><td>Bot:</td><td><b>%(bot)s</b></td>
  <tr><td>Test:</td><td><b>%(test_name)s</b></td>
  <tr><td>Revision Range:</td><td><b>%(start)d - %(end)d</b></td>
</table><p>
<a href="%(graph_url)s">View the graph</a>
and <a href='%(bug_url)s'>file a bug</a>.<br>
<b>+++++++++++++++++++++++++++++++</b><br>
"""

_SUMMARY_EMAIL_TEXT_BODY = """
A %(percent_changed)s %(change_type)s:

Master: %(master)s
Bot: %(bot)s
Test: %(test_name)s
Revision Range:%(start)d - %(end)d

View the graph: %(graph_url)s
File a bug: %(bug_url)s
+++++++++++++++++++++++++++++++
"""

_BUG_REPORT_COMMENT = (
    'Performance dashboard identified a %(percent_changed)s %(change_type)s '
    'in %(test_name)s on %(bot)s at revision range %(start)d:%(end)d. '
    'Graph: %(graph_url)s')

_BUG_REPORT_LINK_URL = (
    'https://code.google.com/p/chromium/issues/entry?summary=%s&comment=%s&'
    'labels=Type-Bug-Regression,Pri-2,Performance-Sheriff,%s')

_ALL_ALERTS_LINK = (
    '<a href="https://chromeperf.appspot.com/alerts?sheriff=%s">'
    'All alerts</a><br>')

_PERF_TRY_EMAIL_SUBJECT = (
    'Perf Try %(status)s on %(bot)s at %(start)s:%(end)s.')

_PERF_TRY_EMAIL_HTML_BODY = """
Perf Try Job %(status)s
<br><br>
A Perf Try Job was submitted on %(bot)s at
<a href="%(perf_url)s">%(perf_url)s</a>.<br>
<table cellpadding='4'>
  <tr><td>Bot:</td><td><b>%(bot)s</b></td>
  <tr><td>Test:</td><td><b>%(command)s</b></td>
  <tr><td>Revision Range:</td><td><b>%(start)s - %(end)s</b></td>
  <tr><td>HTML Results:</td><td><b>%(html_results)s</b></td>
  %(profiler_results)s
</table><p>
"""

_PERF_TRY_EMAIL_TEXT_BODY = """
Perf Try Job %(status)s

Bot: %(bot)s
Test: %(command)s
Revision Range:%(start)s - %(end)s

HTML Results: %(html_results)s
%(profiler_results)s
+++++++++++++++++++++++++++++++
"""

_PERF_PROFILER_HTML_ROW = '<tr><td>%(title)s:</td><td><b>%(link)s</b></td>\n'
_PERF_PROFILER_TEXT_ROW = '%(title)s: %(link)s\n'

_BISECT_FYI_EMAIL_SUBJECT = (
    'Bisect FYI Try Job Failed on %(bot)s for %(test_name)s.')

_BISECT_FYI_EMAIL_HTML_BODY = """
Bisect FYI Try Job Failed
<br><br>
A Bisect FYI Try Job for %(test_name)s was submitted on %(bot)s at
<a href="%(job_url)s">%(job_url)s</a>.<br>
<table cellpadding='4'>
  <tr><td>Bot:</td><td><b>%(bot)s</b></td>
  <tr><td>Test Case:</td><td><b>%(test_name)s</b></td>
  <tr><td>Bisect Config:</td><td><b>%(config)s</b></td>
  <tr><td>Error Details:</td><td><b>%(errors)s</b></td>
  <tr><td>Bisect Results:</td><td><b>%(results)s</b></td>
</table>
"""

_BISECT_FYI_EMAIL_TEXT_BODY = """
Bisect FYI Try Job Failed

Bot: %(bot)s
Test Case: %(test_name)s
Bisect Config: %(config)s
Error Details: %(errors)s
Bisect Results:
%(results)s

+++++++++++++++++++++++++++++++
"""


def GetPerfTryJobEmail(perf_results):
  """Gets the contents of the email to send once a perf try job completes."""
  if perf_results['status'] == 'Completed':
    profiler_html_links = ''
    profiler_text_links = ''
    for title, link in perf_results['profiler_results']:
      profiler_html_links += _PERF_PROFILER_HTML_ROW % {'title': title,
                                                        'link': link}
      profiler_text_links += _PERF_PROFILER_TEXT_ROW % {'title': title,
                                                        'link': link}
    subject_dict = {
        'status': 'Success', 'bot': perf_results['bisect_bot'],
        'start': perf_results['config']['good_revision'],
        'end': perf_results['config']['bad_revision']
    }
    html_dict = {
        'status': 'SUCCESS',
        'bot': perf_results['bisect_bot'],
        'perf_url': perf_results['buildbot_log_url'],
        'command': perf_results['config']['command'],
        'start': perf_results['config']['good_revision'],
        'end': perf_results['config']['bad_revision'],
        'html_results': perf_results['html_results'],
        'profiler_results': profiler_html_links
    }
    text_dict = html_dict.copy()
    text_dict['profiler_results'] = profiler_text_links
  elif perf_results['status'] == 'Failure':
    config = perf_results.get('config')
    if not config:
      config = {
          'good_revision': '?',
          'bad_revision': '?',
          'command': '?',
      }
    subject_dict = {
        'status': 'Failure', 'bot': perf_results['bisect_bot'],
        'start': config['good_revision'],
        'end': config['bad_revision']
    }
    html_dict = {
        'status': 'FAILURE',
        'bot': perf_results['bisect_bot'],
        'perf_url': perf_results['buildbot_log_url'],
        'command': config['command'],
        'start': config['good_revision'],
        'end': config['bad_revision'],
        'html_results': '', 'profiler_results': ''
    }
    text_dict = html_dict
  else:
    return None

  html = _PERF_TRY_EMAIL_HTML_BODY % html_dict
  text = _PERF_TRY_EMAIL_TEXT_BODY % text_dict
  subject = _PERF_TRY_EMAIL_SUBJECT % subject_dict
  return {'subject': subject, 'html': html, 'body': text}


def GetSheriffEmails(sheriff):
  """Gets all of the email addresses to send mail to for a Sheriff.

  This includes both the general email address of the sheriff rotation,
  which is often a mailing list, and the email address of the particular
  sheriff on duty, if applicable.

  Args:
    sheriff: A Sheriff entity.

  Returns:
    A comma-separated list of email addresses; this will be an empty string
    if there are no email addresses.
  """
  receivers = [sheriff.email] if sheriff.email else []
  sheriff_on_duty = _GetSheriffOnDutyEmail(sheriff)
  if sheriff_on_duty:
    receivers.append(sheriff_on_duty)
  return ','.join(receivers)


def _GetSheriffOnDutyEmail(sheriff):
  """Gets the email address of the sheriff on duty for a sheriff rotation.

  Args:
    sheriff: A Sheriff entity.

  Returns:
    A comma-separated list of email addresses, or None.
  """
  if not sheriff.url:
    return None
  response = urlfetch.fetch(sheriff.url)
  if response.status_code != 200:
    logging.error('Response %d from %s for %s.', response.status_code,
                  sheriff.url, sheriff.key.string_id())
    return None
  match = re.match(r'document\.write\(\'(.*)\'\)', response.content)
  if not match:
    logging.error('Could not parse response from sheriff URL %s: %s',
                  sheriff.url, response.content)
    return None
  addresses = match.groups()[0].split(', ')
  return ','.join('%s@google.com' % a for a in addresses)


def GetReportPageLink(test_path, rev=None, add_protocol_and_host=True):
  """Gets a URL for viewing a single graph."""
  path_parts = test_path.split('/')
  if len(path_parts) < 4:
    logging.error('Could not make link, invalid test path: %s', test_path)
  master, bot = path_parts[0], path_parts[1]
  test_name = '/'.join(path_parts[2:])
  trace_name = path_parts[-1]
  trace_names = ','.join([trace_name, trace_name + '_ref', 'ref'])
  if add_protocol_and_host:
    link_template = 'https://chromeperf.appspot.com/report?%s'
  else:
    link_template = '/report?%s'
  uri = link_template % urllib.urlencode([
      ('masters', master),
      ('bots', bot),
      ('tests', test_name),
      ('checked', trace_names),
  ])
  if rev:
    uri += '&rev=%s' % rev
  return uri


def GetGroupReportPageLink(alert):
  """Gets a URL for viewing a graph for an alert and possibly related alerts."""
  # Entities only have a key if they have already been put().
  if alert and alert.key:
    link_template = 'https://chromeperf.appspot.com/group_report?keys=%s'
    return link_template % alert.key.urlsafe()
  # If we can't make the above link, fall back to the /report page.
  test_path = utils.TestPath(alert.test)
  return GetReportPageLink(test_path, rev=alert.end_revision)


def GetAlertInfo(alert, test):
  """Gets the alert info formatted for the given alert and test.

  Args:
    alert: An Anomaly entity.
    test: The Test entity for the given alert.

  Returns:
    A dictionary of string keys to values. Keys are 'email_subject',
    'email_text', 'email_html', 'dashboard_link', 'alerts_link', 'bug_link'.
  """
  percent_changed = alert.GetDisplayPercentChanged()
  change_type = 'improvement' if alert.is_improvement else 'regression'
  test_name = '/'.join(test.test_path.split('/')[2:])
  sheriff_name = alert.sheriff.string_id()
  master = test.master_name
  bot = test.bot_name

  graph_url = GetGroupReportPageLink(alert)

  # Parameters to interpolate into strings below.
  interpolation_parameters = {
      'percent_changed': percent_changed,
      'change_type': change_type,
      'master': master,
      'bot': bot,
      'test_name': test_name,
      'sheriff_name': sheriff_name,
      'start': alert.start_revision,
      'end': alert.end_revision,
      'graph_url': graph_url,
  }

  bug_comment = _BUG_REPORT_COMMENT % interpolation_parameters
  bug_summary = ('%(percent_changed)s %(change_type)s in %(test_name)s '
                 'on %(bot)s at %(start)d:%(end)d') % interpolation_parameters
  labels = bug_label_patterns.GetBugLabelsForTest(test)
  bug_url = _BUG_REPORT_LINK_URL % (
      urllib.quote(bug_summary), urllib.quote(bug_comment), ','.join(labels))

  interpolation_parameters['bug_url'] = bug_url

  results = {
      'email_subject': _SINGLE_EMAIL_SUBJECT % interpolation_parameters,
      'email_text': _SUMMARY_EMAIL_TEXT_BODY % interpolation_parameters,
      'email_html': _EMAIL_HTML_TABLE % interpolation_parameters,
      'dashboard_link': graph_url,
      'alerts_link': _ALL_ALERTS_LINK % urllib.quote(sheriff_name),
      'bug_link': bug_url,
  }
  return results


def GetBisectFYITryJobEmail(job, test_results):
  """Gets the contents of the email to send once a bisect FYI job completes."""
  if test_results['status'] != 'Completed':
    subject_dict = {
        'bot': test_results['bisect_bot'],
        'test_name': job.job_name
    }
    html_dict = {
        'bot': test_results['bisect_bot'],
        'job_url': test_results['buildbot_log_url'],
        'test_name': job.job_name,
        'config': job.config if job.config else 'Undefined',
        'errors': test_results.get('errors'),
        'results': test_results.get('results'),
    }
    text_dict = html_dict
  else:
    return None

  html = _BISECT_FYI_EMAIL_HTML_BODY % html_dict
  text = _BISECT_FYI_EMAIL_TEXT_BODY % text_dict
  subject = _BISECT_FYI_EMAIL_SUBJECT % subject_dict
  return {'subject': subject, 'html': html, 'body': text}
