# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from google.appengine.ext import db
from google.appengine.ext import deferred
from google.appengine.ext import ndb

from dashboard import update_test_suites
from dashboard.common import datastore_hooks
from dashboard.common import descriptor
from dashboard.common import namespaced_stored_object
from dashboard.common import request_handler
from dashboard.common import stored_object
from dashboard.common import utils
from dashboard.models import graph_data
from dashboard.models import histogram
from tracing.value.diagnostics import reserved_infos
from tracing.value.diagnostics import tag_map as tag_map_module


def CacheKey(test_suite):
  return 'test_suite_descriptor_' + test_suite


def FetchCachedTestSuiteDescriptor(test_suite):
  return namespaced_stored_object.Get(CacheKey(test_suite))


class UpdateTestSuiteDescriptorsHandler(request_handler.RequestHandler):

  def get(self):
    self.post()

  def post(self):
    namespace = datastore_hooks.EXTERNAL
    if self.request.get('internal_only') == 'true':
      namespace = datastore_hooks.INTERNAL
    UpdateTestSuiteDescriptors(namespace)


def UpdateTestSuiteDescriptors(namespace):
  key = namespaced_stored_object.NamespaceKey(
      update_test_suites.TEST_SUITES_2_CACHE_KEY, namespace)
  for test_suite in stored_object.Get(key):
    ScheduleUpdateDescriptor(test_suite, namespace)


def ScheduleUpdateDescriptor(test_suite, namespace):
  deferred.defer(_UpdateDescriptor, test_suite, namespace)


def _QueryTestSuite(test_suite):
  desc = descriptor.Descriptor(test_suite=test_suite, bot='place:holder')
  test_path = list(desc.ToTestPathsSync())[0].split('/')

  query = graph_data.TestMetadata.query()
  query = query.filter(graph_data.TestMetadata.suite_name == test_path[2])
  if len(test_path) > 3:
    # test_suite is composite.
    query = query.filter(
        graph_data.TestMetadata.test_part1_name == test_path[3])
  query = query.filter(graph_data.TestMetadata.deprecated == False)
  query = query.filter(graph_data.TestMetadata.has_rows == True)
  return query


def _QueryCaseTags(test_suite, bots):
  test_paths = set()
  for bot in bots:
    desc = descriptor.Descriptor(test_suite=test_suite, bot=bot)
    for test_path in desc.ToTestPathsSync():
      test_paths.add(test_path)

  futures = []
  for test_path in test_paths:
    futures.append(histogram.SparseDiagnostic.GetMostRecentDataByNamesAsync(
        utils.TestKey(test_path), [reserved_infos.TAG_MAP.name]))

  ndb.Future.wait_all(futures)
  tag_map = tag_map_module.TagMap({})
  for future in futures:
    data = future.get_result().get(reserved_infos.TAG_MAP.name)
    if not data:
      continue
    tag_map.AddDiagnostic(tag_map_module.TagMap.FromDict(data))

  return {tag: list(sorted(cases))
          for tag, cases in tag_map.tags_to_story_names.iteritems()}


DEADLINE_SECONDS = 60 * 9.5


def _UpdateDescriptor(test_suite, namespace, start_cursor=None,
                      measurements=(), bots=(), cases=()):
  logging.info('%s %s %d %d %d', test_suite, namespace,
               len(measurements), len(bots), len(cases))

  # This function always runs in the taskqueue as an anonymous user.
  if namespace == datastore_hooks.INTERNAL:
    datastore_hooks.SetPrivilegedRequest()

  start = time.time()
  deadline = start + DEADLINE_SECONDS
  key_count = 0
  measurements = set(measurements)
  bots = set(bots)
  cases = set(cases)

  # Some test suites have more keys than can fit in memory or can be processed
  # in 10 minutes, so use an iterator instead of a page limit.
  query_iter = _QueryTestSuite(test_suite).iter(
      keys_only=True, produce_cursors=True, start_cursor=start_cursor,
      use_cache=False, use_memcache=False)

  try:
    for key in query_iter:
      key_count += 1
      desc = descriptor.Descriptor.FromTestPathSync(utils.TestPath(key))
      bots.add(desc.bot)
      if desc.measurement:
        measurements.add(desc.measurement)
      if desc.test_case:
        cases.add(desc.test_case)
      if time.time() > deadline:
        break
  except db.BadRequestError:
    pass

  logging.info('%d keys, %d measurements, %d bots, %d cases',
               key_count, len(measurements), len(bots), len(cases))
  if key_count:
    logging.info('per_key:wall_us=%f',
                 round(1e6 * (time.time() - start) / key_count))

  if query_iter.probably_has_next():
    logging.info('continuing')
    deferred.defer(_UpdateDescriptor, test_suite, namespace,
                   query_iter.cursor_before(), measurements, bots, cases)
    return

  desc = {
      'measurements': list(sorted(measurements)),
      'bots': list(sorted(bots)),
      'cases': list(sorted(cases)),
  }

  case_tags = _QueryCaseTags(test_suite, bots)
  if case_tags:
    desc['caseTags'] = case_tags

  key = namespaced_stored_object.NamespaceKey(
      CacheKey(test_suite), namespace)
  stored_object.Set(key, desc)
