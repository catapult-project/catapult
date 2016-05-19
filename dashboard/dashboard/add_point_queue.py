# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""URL endpoint to add new graph data to the datastore."""

import json
import logging

from google.appengine.api import datastore_errors
from google.appengine.ext import ndb

from dashboard import add_point
from dashboard import datastore_hooks
from dashboard import find_anomalies
from dashboard import graph_revisions
from dashboard import request_handler
from dashboard import stored_object
from dashboard import units_to_direction
from dashboard import utils
from dashboard.models import anomaly
from dashboard.models import graph_data

BOT_WHITELIST_KEY = 'bot_whitelist'


class AddPointQueueHandler(request_handler.RequestHandler):
  """Request handler to process points and add them to the datastore.

  This request handler is intended to be used only by requests using the
  task queue; it shouldn't be directly from outside.
  """

  def get(self):
    """A get request is the same a post request for this endpoint."""
    self.post()

  def post(self):
    """Adds a set of points from the post data.

    Request parameters:
      data: JSON encoding of a list of dictionaries. Each dictionary represents
          one point to add. For each dict, one Row entity will be added, and
          any required Test or Master or Bot entities will be created.
    """
    datastore_hooks.SetPrivilegedRequest()

    data = json.loads(self.request.get('data'))
    _PrewarmGets(data)

    bot_whitelist = stored_object.Get(BOT_WHITELIST_KEY)

    all_put_futures = []
    added_rows = []
    monitored_test_keys = []
    for row_dict in data:
      try:
        new_row, parent_test, put_futures = _AddRow(row_dict, bot_whitelist)
        added_rows.append(new_row)
        is_monitored = parent_test.sheriff and parent_test.has_rows
        if is_monitored:
          monitored_test_keys.append(parent_test.key)
        all_put_futures.extend(put_futures)

      except add_point.BadRequestError as e:
        logging.error('Could not add %s, it was invalid.', e.message)
      except datastore_errors.BadRequestError as e:
        logging.error('Datastore request failed: %s.', e.message)
        return

    ndb.Future.wait_all(all_put_futures)

    # Updating of the cached graph revisions should happen after put because
    # it requires the new row to have a timestamp, which happens upon put.
    graph_revisions.AddRowsToCache(added_rows)

    for test_key in monitored_test_keys:
      if not _IsRefBuild(test_key):
        find_anomalies.ProcessTest(test_key)
      else:
        logging.warn('Ref data marked as monitored: %s', str(test_key))


def _PrewarmGets(data):
  """Prepares the cache so that fetching is faster later.

  The add_point request handler does a LOT of gets, and it's possible for
  each to take seconds.

  However, NDB will does automatic in-context caching:
  https://developers.google.com/appengine/docs/python/ndb/cache#incontext
  This means that doing an async get() at the start will cache the result, so
  that we can prewarm the cache for everything we'll need throughout the
  request at the start.

  Args:
    data: The request json.
  """
  # Prewarm lookups of masters, bots, and tests.
  master_keys = {ndb.Key('Master', r['master']) for r in data}
  bot_keys = {ndb.Key('Master', r['master'], 'Bot', r['bot']) for r in data}
  test_keys = set()
  for row in data:
    start = ['Master', row['master'], 'Bot', row['bot']]
    test_parts = row['test'].split('/')
    for part in test_parts:
      if not part:
        break
      start += ['Test', part]
      test_keys.add(ndb.Key(*start))

  ndb.get_multi_async(list(master_keys) + list(bot_keys) + list(test_keys))


def _AddRow(row_dict, bot_whitelist):
  """Adds a Row entity to the datastore.

  There are three main things that are needed in order to make a new entity;
  the ID, the parent key, and all of the properties. Making these three
  things, and validating the related input fields, are delegated to
  sub-functions.

  Args:
    row_dict: A dictionary obtained from the JSON that was received.
    bot_whitelist: A list of whitelisted bots names.

  Returns:
    A triple: The new row, the parent test, and a list of entity put futures.

  Raises:
    add_point.BadRequestError: The input dict was invalid.
    RuntimeError: The required parent entities couldn't be created.
  """
  parent_test = _GetParentTest(row_dict, bot_whitelist)
  test_container_key = utils.GetTestContainerKey(parent_test.key)

  columns = add_point.GetAndValidateRowProperties(row_dict)
  columns['internal_only'] = parent_test.internal_only

  row_id = add_point.GetAndValidateRowId(row_dict)

  # Update the last-added revision record for this test.
  master, bot, test = row_dict['master'], row_dict['bot'], row_dict['test']
  test_path = '%s/%s/%s' % (master, bot, test)
  last_added_revision_entity = graph_data.LastAddedRevision(
      id=test_path, revision=row_id)
  entity_put_futures = []
  entity_put_futures.append(last_added_revision_entity.put_async())

  # If the row ID isn't the revision, that means that the data is Chrome OS
  # data, and we want the default revision to be Chrome version.
  if row_id != row_dict.get('revision'):
    columns['a_default_rev'] = 'r_chrome_version'

  # Create the entity and add it asynchronously.
  new_row = graph_data.Row(id=row_id, parent=test_container_key, **columns)
  entity_put_futures.append(new_row.put_async())

  return new_row, parent_test, entity_put_futures


def _GetParentTest(row_dict, bot_whitelist):
  """Gets the parent test for a Row based on an input dictionary.

  Args:
    row_dict: A dictionary from the data parameter.
    bot_whitelist: A list of whitelisted bot names.

  Returns:
    A Test entity.

  Raises:
    RuntimeError: Something went wrong when trying to get the parent Test.
  """
  master_name = row_dict.get('master')
  bot_name = row_dict.get('bot')
  test_name = row_dict.get('test').strip('/')
  units = row_dict.get('units')
  higher_is_better = row_dict.get('higher_is_better')
  improvement_direction = _ImprovementDirection(higher_is_better)
  internal_only = _BotInternalOnly(bot_name, bot_whitelist)
  benchmark_description = row_dict.get('benchmark_description')

  parent_test = _GetOrCreateAncestors(
      master_name, bot_name, test_name, units=units,
      improvement_direction=improvement_direction,
      internal_only=internal_only,
      benchmark_description=benchmark_description)

  return parent_test


def _ImprovementDirection(higher_is_better):
  """Returns an improvement direction (constant from alerts_data) or None."""
  if higher_is_better is None:
    return None
  return anomaly.UP if higher_is_better else anomaly.DOWN


def _BotInternalOnly(bot_name, bot_whitelist):
  """Checks whether a given bot name is internal-only.

  If a bot name is internal only, then new data for that bot should be marked
  as internal-only.
  """
  if not bot_whitelist:
    logging.warning(
        'No bot whitelist available. All data will be internal-only. If this '
        'is not intended, please add a bot whitelist using /edit_site_config.')
    return True
  return bot_name not in bot_whitelist


def _GetOrCreateAncestors(
    master_name, bot_name, test_name, units=None,
    improvement_direction=None, internal_only=True, benchmark_description=''):
  """Gets or creates all necessary Master, Bot and Test entities for a Row."""

  master_entity = _GetOrCreateMaster(master_name)
  bot_entity = _GetOrCreateBot(
      bot_name, master_entity.key, internal_only)

  # Add all ancestor tests to the datastore in order.
  ancestor_test_parts = test_name.split('/')

  parent = bot_entity
  suite = None
  for index, ancestor_test_name in enumerate(ancestor_test_parts):
    # Certain properties should only be updated if the Test is a leaf test.
    is_leaf_test = (index == len(ancestor_test_parts) - 1)
    test_properties = {
        'units': units if is_leaf_test else None,
        'improvement_direction': (improvement_direction
                                  if is_leaf_test else None),
        'internal_only': internal_only,
    }
    ancestor_test = _GetOrCreateTest(
        ancestor_test_name, parent.key, test_properties)
    if index == 0:
      suite = ancestor_test
    parent = ancestor_test
  if benchmark_description and suite.description != benchmark_description:
    suite.description = benchmark_description
  return parent


def _GetOrCreateMaster(name):
  """Gets or creates a new Master."""
  existing = graph_data.Master.get_by_id(name)
  if existing:
    return existing
  new_entity = graph_data.Master(id=name)
  new_entity.put()
  return new_entity


def _GetOrCreateBot(name, parent_key, internal_only):
  """Gets or creates a new Bot under the given Master."""
  existing = graph_data.Bot.get_by_id(name)
  if existing:
    return existing
  new_entity = graph_data.Bot(
      id=name, parent=parent_key, internal_only=internal_only)
  new_entity.put()
  return new_entity


def _GetOrCreateTest(name, parent_key, properties):
  """Either gets an entity if it already exists, or creates one.

  If the entity already exists but the properties are different than the ones
  specified, then the properties will be updated first. This implies that a
  new point is being added for an existing Test, so if the Test has been
  previously marked as deprecated or associated with a stoppage alert, then it
  can be updated and marked as non-deprecated.

  If the entity doesn't yet exist, a new one will be created with the given
  properties.

  Args:
    name: The string ID of the Test to get or create.
    parent_key: The key of the parent entity.
    properties: A dictionary of properties that should be set.

  Returns:
    An entity (which has already been put).

  Raises:
    datastore_errors.BadRequestError: Something went wrong getting the entity.
  """
  existing = graph_data.Test.get_by_id(name, parent_key)

  if not existing:
    # Add improvement direction if this is a new test.
    if 'units' in properties:
      units = properties['units']
      direction = units_to_direction.GetImprovementDirection(units)
      properties['improvement_direction'] = direction
    new_entity = graph_data.Test(id=name, parent=parent_key, **properties)
    new_entity.put()
    return new_entity

  # Flag indicating whether we want to re-put the entity before returning.
  properties_changed = False

  if existing.deprecated:
    existing.deprecated = False
    properties_changed = True

  if existing.stoppage_alert:
    alert = existing.stoppage_alert.get()
    if alert:
      alert.recovered = True
      alert.put()
    else:
      logging.warning('Stoppage alert %s not found.', existing.stoppage_alert)
    existing.stoppage_alert = None
    properties_changed = True

  # Special case to update improvement direction from units for Test entities
  # when units are being updated. If an improvement direction is explicitly
  # provided in the properties, then it will be updated again below.
  units = properties.get('units')
  if units:
    direction = units_to_direction.GetImprovementDirection(units)
    if direction != existing.improvement_direction:
      existing.improvement_direction = direction
      properties_changed = True

  # Go through the list of general properties and update if necessary.
  for prop, value in properties.items():
    if (hasattr(existing, prop) and value is not None and
        getattr(existing, prop) != value):
      setattr(existing, prop, value)
      properties_changed = True

  if properties_changed:
    existing.put()
  return existing


def _IsRefBuild(test_key):
  """Checks whether a Test is for a reference build test run."""
  key_path = test_key.flat()
  return key_path[-1] == 'ref' or key_path[-1].endswith('_ref')
