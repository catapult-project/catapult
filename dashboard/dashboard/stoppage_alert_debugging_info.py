# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""URI endpoint to fill in dialog for debugging data stoppage alerts."""

import json
import re

from google.appengine.ext import ndb

from dashboard.common import request_handler
from dashboard.common import utils
from dashboard.models import graph_data
from dashboard.services import milo_service


class StoppageAlertDebuggingInfoHandler(request_handler.RequestHandler):

  def post(self):
    """Returns JSON data about a data stoppage for debugging dialog.

    Request parameters:
      key: Key of the data stoppage alert to debug; test_path and rev are
          ignored if key is specified.
      test_path: Test path of the test to debug; ignored if key is specified.
      rev: Point id of the last known revision; ignored if key is specified.

    Outputs:
      JSON which gives as many debugging details as possible.
    """
    stoppage_details = {}
    row = None
    if self.request.get('key'):
      alert = ndb.Key(urlsafe=self.request.get('key')).get()
      if not alert:
        self.response.out.write(json.dumps({'error': 'Invalid alert key'}))
        return
      row = alert.row.get()
    else:
      # Grab row from test_path and rev.
      rev = self.request.get('rev')
      try:
        rev = int(rev)
      except TypeError:
        self.response.out.write(json.dumps({'error': 'Invalid rev'}))
        return
      test_path = self.request.get('test_path')
      if not test_path:
        self.response.out.write(json.dumps({'error': 'No test specified'}))
        return

      row = graph_data.Row.get_by_id(
          rev, parent=ndb.Key('TestContainer', test_path))

    if not row:
      self.response.out.write(json.dumps({'error': 'No row for alert.'}))
      return

    test_path = utils.TestPath(row.key.parent())
    stoppage_details['test_path'] = test_path

    current_stdio_link = (getattr(row, 'a_stdio_uri', None) or
                          getattr(row, 'a_a_stdio_uri', None))
    if not current_stdio_link:
      self.response.out.write(json.dumps({'error': 'Cannot find stdio link.'}))
      return
    _, master, bot, current_buildnumber, step = (
        utils.GetBuildDetailsFromStdioLink(current_stdio_link))
    if not master or not current_buildnumber:
      self.response.out.write(json.dumps({'error': 'Cannot parse stdio link.'}))
      return
    next_buildnumber = str(int(current_buildnumber) + 1)
    next_stdio_link = current_stdio_link.replace(
        current_buildnumber, next_buildnumber)

    stoppage_details['current_logdog_uri'] = (
        utils.GetLogdogLogUriFromStdioLink(current_stdio_link))
    stoppage_details['current_buildbot_status_page'] = (
        utils.GetBuildbotStatusPageUriFromStdioLink(current_stdio_link))
    stoppage_details['next_logdog_uri'] = (
        utils.GetLogdogLogUriFromStdioLink(next_stdio_link))
    stoppage_details['next_buildbot_status_page'] = (
        utils.GetBuildbotStatusPageUriFromStdioLink(next_stdio_link))

    current_build_info = milo_service.GetBuildbotBuildInfo(
        master, bot, current_buildnumber)
    stoppage_details['current_commit_pos'] = row.key.id()
    if current_build_info:
      commit_pos_str = current_build_info['properties']['got_revision_cp']
      stoppage_details['current_commit_pos'] = re.match(
          r'.*\{#(\d+)\}', commit_pos_str).group(1)
      current_result = current_build_info['steps'].get(step)
      if current_result:
        current_result = current_result.get('results')
      stoppage_details['current_result'] = current_result

    next_build_info = milo_service.GetBuildbotBuildInfo(
        master, bot, next_buildnumber)
    stoppage_details['next_commit_pos'] = None
    stoppage_details['next_result'] = None
    if next_build_info:
      commit_pos_str = next_build_info['properties']['got_revision_cp']
      stoppage_details['next_commit_pos'] = re.match(
          r'.*\{#(\d+)\}', commit_pos_str).group(1)
      next_result = next_build_info['steps'].get(step)
      if next_result:
        next_result = next_result.get('results')
      stoppage_details['next_result'] = next_result

    self.response.out.write(json.dumps(stoppage_details))
