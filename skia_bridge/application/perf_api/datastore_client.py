# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import

from enum import Enum
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


class EntityType(Enum):
  """Enum defining the entity types currently supported."""
  Anomaly = 'Anomaly'
  AlertGroup = 'AlertGroup'
  TestMetadata = 'TestMetadata'


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
        lambda a: a.get('end_revision') >= int(min_revision),
        lambda a: a.get('end_revision') <= int(max_revision),
        # TODO: Remove the check below once we fully enable anomalies from skia
        lambda a: a.get('source', None) == None,
    ]
    results = list(ds_query.fetch())
    filtered_results = [
        alert for alert in results if all(
            post_filter(alert) for post_filter in post_query_filters)
    ]
    return filtered_results

  def QueryAlertGroups(self, group_name, group_type):
    query = self._client.query(kind='AlertGroup')
    query.add_filter('active', '=', True)
    query.add_filter('name', '=', group_name)

    results = list(query.fetch())
    filtered_results = [
      group for group in results if group['group_type'] == group_type
    ]

    return filtered_results

  def GetEntity(self, entity_type:EntityType, entity_id):
    """Retrieves an entity of the specified type with the specified id."""
    entity_key = self._client.key(entity_type.value, entity_id)
    return self._client.get(entity_key)

  def GetEntities(self, entity_type:EntityType, entity_ids:[]):
    """Retrieves multiple entities of the specified type."""
    entity_keys = [self._client.key(entity_type.value, entity_id)
                   for entity_id in entity_ids]
    return self._client.get_multi(entity_keys)

  def CreateEntity(self,
                   entity_type:EntityType,
                   entity_id,
                   entity_values:dict,
                   save:bool = False):
    """Creates a new entity of the specified type with the supplied values"""
    entity = datastore.Entity(self._client.key(entity_type.value, entity_id))
    entity.update(entity_values)
    if save:
      self._client.put(entity)
    return entity

  def PutEntities(self, entities:[], transaction=False):
    if transaction:
      with self._client.transaction():
        self._client.put_multi(entities)
    else:
      self._client.put_multi(entities)
