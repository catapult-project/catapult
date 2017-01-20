# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides the speed releasing table."""

import json

from google.appengine.ext import ndb

from dashboard.common import request_handler
from dashboard.models import table_config


class SpeedReleasingHandler(request_handler.RequestHandler):
  """Request handler for requests for speed releasing page."""

  def get(self, *args):  # pylint: disable=unused-argument
    """Renders the UI for the speed releasing page."""
    self.RenderStaticHtml('speed_releasing.html')

  def post(self, *args):
    """Returns dynamic data for /speed_releasing.

    Outputs:
      JSON for the /speed_releasing page XHR request.
    """
    if args[0]:
      self._OutputTableJSON(args[0])
    else:
      self._OutputHomePageJSON()

  def _OutputTableJSON(self, table_name):
    table_entity = ndb.Key('TableConfig', table_name).get()
    if not table_entity:
      self.response.out.write(json.dumps({'error': 'Invalid table name.'}))
      return
    values = {}
    self.GetDynamicVariables(values)
    master_bot_pairs = []
    for bot in table_entity.bots:
      master_bot_pairs.append(bot.parent().string_id() +
                              '/' + bot.string_id())
    self.response.out.write(json.dumps({
        'xsrf_token': values['xsrf_token'],
        'table_bots': master_bot_pairs,
        'table_tests': table_entity.tests,
        'table_layout': table_entity.table_layout,
        'name': table_entity.key.string_id(),
    }))

  def _OutputHomePageJSON(self):
    all_entities = table_config.TableConfig.query().fetch()
    list_of_entities = []
    for entity in all_entities:
      list_of_entities.append(entity.key.string_id())
    self.response.out.write(json.dumps({
        'show_list': True,
        'list': list_of_entities
    }))
