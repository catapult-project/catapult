# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import

from google.cloud import datastore


def TestKey(test_path, datastore_client):
  """Returns the key that corresponds to a test path."""
  if test_path is None:
    return None
  path_parts = test_path.split('/')
  if path_parts is None:
    return None
  if len(path_parts) < 3:
    key_list = [('Master', path_parts[0])]
    if len(path_parts) > 1:
      key_list += [('Bot', path_parts[1])]
    return datastore_client.key(pairs=key_list)
  return datastore_client.key('TestMetadata', test_path)


class DataStoreClient:
  _client = datastore.Client()

  def QueryAnomalies(self, tests, min_revision, max_revision):
    ds_query = self._client.query(kind='Anomaly')
    test_keys = [TestKey(test_path, self._client) for test_path in tests]
    ds_query.add_filter('test', 'IN', test_keys)

    # Due to the way the indexes in Datastore work, we can one inequality
    # property we can filter on. With the 'test' filter above, the key
    # becomes the inequality property. Hence, in order to filter by revision,
    # we need to apply the filters after the results are retrieved from
    # datastore.
    post_query_filters = [
        lambda a: a.get('start_revision') >= int(min_revision),
        lambda a: a.get('start_revision') <= int(max_revision),
    ]
    results = list(ds_query.fetch())
    filtered_results = [
        alert for alert in results if all(
            post_filter(alert) for post_filter in post_query_filters)
    ]
    return filtered_results
