# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides the speed releasing table."""

import collections
import json

from google.appengine.ext import ndb

from dashboard.common import request_handler
from dashboard.common import utils
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
    """Obtains the JSON values that comprise the table.

    Args:
      table_name: The name of the requested report.
    """
    table_entity = ndb.Key('TableConfig', table_name).get()
    if not table_entity:
      self.response.out.write(json.dumps({'error': 'Invalid table name.'}))
      return

    values = {}
    self.GetDynamicVariables(values)

    master_bot_pairs = _GetMasterBotPairs(table_entity.bots)

    rev_a = self.request.get('revA')
    rev_b = self.request.get('revB')
    if not rev_a or not rev_b:
      self.response.out.write(json.dumps({'error': 'Invalid revisions.'}))
      return
    rev_a, rev_b = _CheckRevisions(rev_a, rev_b)
    revisions = [rev_a, rev_b]

    self.response.out.write(json.dumps({
        'xsrf_token': values['xsrf_token'],
        'table_bots': master_bot_pairs,
        'table_tests': table_entity.tests,
        'table_layout': json.loads(table_entity.table_layout),
        'name': table_entity.key.string_id(),
        'values': _GetRowValues(revisions, master_bot_pairs,
                                table_entity.tests),
        'units': _GetTestToUnitsMap(master_bot_pairs, table_entity.tests),
        'revisions': revisions,
        'categories': _GetCategoryCounts(json.loads(table_entity.table_layout)),
    }))

  def _OutputHomePageJSON(self):
    """Returns a list of reports a user has permission to see."""
    all_entities = table_config.TableConfig.query().fetch()
    list_of_entities = []
    for entity in all_entities:
      list_of_entities.append(entity.key.string_id())
    self.response.out.write(json.dumps({
        'show_list': True,
        'list': list_of_entities
    }))

def _GetMasterBotPairs(bots):
  master_bot_pairs = []
  for bot in bots:
    master_bot_pairs.append(bot.parent().string_id() + '/' + bot.string_id())
  return master_bot_pairs

def _GetRowValues(revisions, bots, tests):
  """Builds a nested dict organizing values by rev/bot/test.

  Args:
    revisions: The revisions to get values for.
    bots: The Master/Bot pairs the tables cover.
    tests: The tests that go in each table.

  Returns:
    A dict with the following structure:
    revisionA: {
      bot1: {
        test1: value,
        test2: value,
        ...
      }
      ...
    }
    revisionB: {
      ...
    }
  """
  row_values = {}
  for rev in revisions:
    bot_values = {}
    for bot in bots:
      test_values = {}
      for test in tests:
        test_values[test] = _GetRow(bot, test, rev)
      bot_values[bot] = test_values
    row_values[rev] = bot_values
  return row_values

def _GetTestToUnitsMap(bots, tests):
  """Grabs the units on each test for only one bot."""
  units_map = {}
  if bots:
    bot = bots[0]
  for test in tests:
    test_path = bot + '/' + test
    test_entity = utils.TestMetadataKey(test_path).get()
    if test_entity:
      units_map[test] = test_entity.units
  return units_map

def _GetRow(bot, test, rev):
  test_path = bot + '/' + test
  test_key = utils.TestKey(test_path)
  row_key = utils.GetRowKey(test_key, rev)
  if row_key.get():
    return row_key.get().value
  else:
    return 0

def _CheckRevisions(rev_a, rev_b):
  """Checks to ensure the revisions are valid."""
  rev_a = int(rev_a)
  rev_b = int(rev_b)
  if rev_b < rev_a:
    rev_a, rev_b = rev_b, rev_a
  # TODO(jessimb): Check if r_commit_pos (if clank), if so return revision.
  return rev_a, rev_b

def _GetCategoryCounts(layout):
  categories = collections.defaultdict(lambda: 0)
  for test in layout:
    categories[layout[test][0]] += 1
  return categories
