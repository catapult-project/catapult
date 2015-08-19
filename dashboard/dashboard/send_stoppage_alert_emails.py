# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A request handler to send alert summary emails to sheriffs on duty."""

from google.appengine.api import mail
from google.appengine.ext import ndb

from dashboard import datastore_hooks
from dashboard import email_template
from dashboard import request_handler
from dashboard import test_owner
from dashboard import utils
from dashboard.models import sheriff
from dashboard.models import stoppage_alert

_HTML_BODY_TEMPLATE = """
<p>Tests that have not received data in some time:</p>
<table>
  <tr><th>Last rev</th><th>Test</th><th>Stdio</th></tr>
  %(alert_rows)s
</table>
<p>Relevant test owners: %(test_owners)s</p>
<p>It is possible that the test has been failing, or that the test was
disabled on purpose and we should remove monitoring. It is also possible
that the test has been renamed and the monitoring should be updated.
<a href="%(bug_template_link)s">File a bug.</a></p>
"""
_HTML_ALERT_ROW_TEMPLATE = """<tr>
    <td>%(rev)d</td>
    <td><a href="%(graph_link)s">%(test_path)s</a></td>
    <td><a href="%(stdio_link)s">stdio</a></td>
  </tr>
"""
_TEXT_BODY_TEMPLATE = """
Tests that have not received data in some time:
%(alert_rows)s

Relevant test owners: %(test_owners)s

It is possible that the test has been failing, or that the test was
disabled on purpose and we should remove monitoring. It is also possible
that the test has been renamed and the monitoring should be updated.

File a bug: %(bug_template_link)s
"""
_TEXT_ALERT_ROW_TEMPLATE = """
  Last rev: %(rev)d
  Test: %(test_path)s
  Graph:%(graph_link)s
  Stdio: %(stdio_link)s
"""
_BUG_TEMPLATE_URL = (
    'https://code.google.com/p/chromium/issues/entry'
    '?labels=Pri-1,Performance-Waterfall,Performance-Sheriff,'
    'Type-Bug-Regression,OS-?&comment=Tests affected:'
    '&summary=No+data+received+for+<tests>+since+<rev>'
    'cc=%s')


class SendStoppageAlertEmailsHandler(request_handler.RequestHandler):
  """Sends emails to sheriffs about stoppage alerts in the past day.

  This request handler takes no parameters and is intended to be called by cron.
  """

  def get(self):
    """Emails sheriffs about new stoppage alerts."""
    datastore_hooks.SetPrivilegedRequest()
    sheriffs_to_email_query = sheriff.Sheriff.query(
        sheriff.Sheriff.stoppage_alert_delay > 0)
    for sheriff_entity in sheriffs_to_email_query:
      _SendStoppageAlertEmail(sheriff_entity)


def _SendStoppageAlertEmail(sheriff_entity):
  """Sends a summary email for the given sheriff rotation.

  Args:
    sheriff_entity: A Sheriff key.
  """
  stoppage_alerts = _RecentStoppageAlerts(sheriff_entity)
  if not stoppage_alerts:
    return
  alert_dicts = [_AlertRowDict(a) for a in stoppage_alerts]
  test_owners = _TestOwners(stoppage_alerts)
  mail.send_mail(
      sender='gasper-alerts@google.com',
      to=email_template.GetSheriffEmails(sheriff_entity),
      subject=_Subject(sheriff_entity, stoppage_alerts),
      body=_TextBody(alert_dicts, test_owners),
      html=_HtmlBody(alert_dicts, test_owners))
  for alert in stoppage_alerts:
    alert.mail_sent = True
  ndb.put_multi(stoppage_alerts)


def _RecentStoppageAlerts(sheriff_entity):
  """Returns new StoppageAlert entities that have not had a mail sent yet."""
  return stoppage_alert.StoppageAlert.query(
      stoppage_alert.StoppageAlert.sheriff == sheriff_entity.key,
      stoppage_alert.StoppageAlert.mail_sent == False).fetch()


def _Subject(sheriff_entity, stoppage_alerts):
  """Returns the subject line for an email about stoppage alerts.

  Args:
    sheriff_entity: The Sheriff who will receive the alerts.
    stoppage_alerts: A list of StoppageAlert entities.

  Returns:
    A string email subject line.
  """
  template = 'No data received in at least %d days for %d series.'
  return template % (sheriff_entity.stoppage_alert_delay, len(stoppage_alerts))


def _HtmlBody(alert_dicts, test_owners):
  """Returns the HTML body for an email about stoppage alerts."""
  html_alerts = '\n'.join(_HTML_ALERT_ROW_TEMPLATE % a for a in alert_dicts)
  return _HTML_BODY_TEMPLATE % {
      'alert_rows': html_alerts,
      'bug_template_link': _BUG_TEMPLATE_URL % test_owners,
      'test_owners': test_owners,
  }


def _TextBody(alert_dicts, test_owners):
  """Returns the text body for an email about stoppage alerts."""
  text_alerts = '\n'.join(_TEXT_ALERT_ROW_TEMPLATE % a for a in alert_dicts)
  return _TEXT_BODY_TEMPLATE % {
      'alert_rows': text_alerts,
      'bug_template_link': _BUG_TEMPLATE_URL % test_owners,
      'test_owners': test_owners,
  }


def _AlertRowDict(alert):
  """Returns a dict with information to print about one stoppage alert."""
  test_path = utils.TestPath(alert.test)
  return {
      'rev': alert.revision,
      'test_path': test_path,
      'graph_link': email_template.GetReportPageLink(test_path),
      'stdio_link': _StdioLink(alert),
  }


def _StdioLink(alert):
  """Returns a list of stdio log links for the given stoppage alerts."""
  row = alert.row.get()
  return getattr(row, 'a_stdio_uri', None)


def _TestOwners(stoppage_alerts):
  """Returns a list of test owners for the given alerts."""
  def SuitePath(alert):
    path_parts = utils.TestPath(alert.test).split('/')
    return '%s/%s' % (path_parts[0], path_parts[2])
  test_owners = test_owner.GetOwners([SuitePath(a) for a in stoppage_alerts])
  return ','.join(test_owners)
