# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""API Wrapper for the luci-config service."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from google.cloud import datastore
from googleapiclient import errors
from googleapiclient.discovery import build
import base64
import fnmatch
import httplib2
import re
import sheriff_pb2
import validator

# The Root of the luci-config API service.
API_ROOT = 'https://luci-config.appspot.com/_ah/api'

# The path which we will look for in projects.
SHERIFF_CONFIG_PATH = 'chromeperf-sheriff.cfg'


class Error(Exception):
  """All errors associated with the luci_config module."""


class FetchError(Error):

  def __init__(self, error):
    super(FetchError,
          self).__init__('Failed fetching project configs: {}'.format(error))
    self.error = error


class DiscoveryError(Error):

  def __init__(self, error):
    super(DiscoveryError,
          self).__init__('Service discovery failed: {}'.format(error))
    self.error = error


class InvalidConfigError(Error):

  def __init__(self, config, fields):
    super(InvalidConfigError, self).__init__(
        'Config (%r) missing required fields: %r' % (config, fields))
    self.fields = fields
    self.config = config


class InvalidContentError(Error):

  def __init__(self, error, config):
    super(InvalidContentError, self).__init__(
        'Config (%r) content decoding error: %s' % (config, error))
    self.config = config
    self.error = error


def CreateConfigClient(http,
                       api_root=API_ROOT,
                       api='config',
                       version='v1',
                       credentials=None):
  """Factory function for a creating a config client.

  This uses the discovery API to generate a service object corresponding to the
  API we're using from luci-config.

  Args:
    http: a fully configured HTTP client/request
    api_root: the URL through which the API will be configured (default:
      API_ROOT)
    api: the service name (default: 'config')
    version: the version of the API (default: 'v1')
    credentials: a google.auth.Credential, directly supported by the
      googleapiclient library (default: None)
  """
  discovery_url = '%s/discovery/v1/apis/%s/%s/rest' % (api_root, api, version)
  try:
    if not credentials:
      client = build(api, version, discoveryServiceUrl=discovery_url, http=http)
    else:
      client = build(
          api,
          version,
          discoveryServiceUrl=discovery_url,
          credentials=credentials)
  except (errors.HttpError, errors.UnknownApiNameOrVersion) as e:
    raise DiscoveryError(e)
  return client


def FindAllSheriffConfigs(client):
  """Finds all the project configs for chromeperf sheriffs."""
  try:
    configs = client.get_project_configs(path=SHERIFF_CONFIG_PATH).execute()
  except (errors.HttpError, httplib2.HttpLib2Error) as e:
    raise FetchError(e)
  return configs


def StoreConfigs(client, configs):
  """Takes configuration dictionaries and persists them in the datastore.

  Args:
    client: The client for accessing the storage API.
    configs: The config objects we'd like to store.

  Raises:
    InvalidConfigError: raised when config has missing required fields.
    InvalidConfigFieldError: raised when the content is not a decodable base64
      encoded JSON document.

  Returns:
    None
  """
  # We group the Subscription instances along a SubscriptionIndex entity. A
  # SubscriptionIndex will always have the latest version of the subscription
  # configurations, for easy lookup, as a list. We will only update the
  # SubscriptionIndex if there were any new revisions in the configuration sets
  # that we've gotten.
  subscription_index_key = client.key('SubscriptionIndex', 'global')

  if not configs:
    # We should clear the existing set of configs, if there are any.
    with client.transaction():
      subscription_index = datastore.Entity(
          key=subscription_index_key, exclude_from_indexes=['config_sets'])
      subscription_index.update({'config_sets': []})
      client.put(subscription_index)
      return

  required_fields = {'config_set', 'content', 'revision', 'url', 'content_hash'}

  def Transform(config):
    missing_fields = required_fields.difference(config)
    if len(missing_fields):
      raise InvalidConfigError(config, missing_fields)

    # We use a combination of the config set, revision, and content_hash to
    # identify this particular configuration.
    key = client.key(
        'Subscription',
        '{config_set}:{revision}'.format(**config),
        parent=subscription_index_key)
    try:
      sheriff_config = validator.Validate(
          base64.standard_b64decode(config['content']))
    except validator.Error as error:
      raise InvalidContentError(config, error)

    entity = datastore.Entity(
        key=key, exclude_from_indexes=['sheriff_config', 'url'])
    entity.update({
        'config_set': config['config_set'],
        'revision': config['revision'],
        'content_hash': config['content_hash'],
        'url': config['url'],
        'sheriff_config': sheriff_config.SerializeToString()
    })
    return (key, entity)

  entities = dict(Transform(config) for config in configs)
  with client.transaction():
    # First, lookup the keys for each of the entities to see whether all of them
    # have already been stored. This allows us to avoid performing write
    # operations that end up not doing any updates.
    found_entities = client.get_multi(entities)

    # Next, we only put the entities that are missing.
    for found_entity in found_entities:
      del entities[found_entity.key]

    # From here we'll update an entity in the datastore which lists the grouped
    # keys in the datastore. This will serve as an index on the latest set of
    # configurations.
    subscription_index = datastore.Entity(
        key=subscription_index_key, exclude_from_indexes=['config_sets'])
    subscription_index.update({
        'config_sets': [
            '{config_set}:{revision}'.format(**config) for config in configs
        ]
    })
    client.put_multi(list(entities.values()) + [subscription_index])


def FindMatchingConfigs(client, request):
  """Yield tuples of (config_set, revision, subscription)."""
  with client.transaction(read_only=True):
    # First look up the global index.
    subscription_index_key = client.key('SubscriptionIndex', 'global')
    subscription_index = client.get(subscription_index_key)
    if subscription_index is None:
      return

    # Then for each instance in the 'config_sets', create a key based on the
    # subscription_index_key as a parent, and look those up in one go.
    config_sets = client.get_multi([
        client.key('Subscription', key, parent=subscription_index_key)
        for key in subscription_index['config_sets']
    ])

  # From there we can then go through each of the subscriptions in the retrieved
  # configs, and yield the ones that have patterns applying to the request.
  for config in config_sets:
    sheriff_config = sheriff_pb2.SheriffConfig()
    sheriff_config.ParseFromString(config['sheriff_config'])
    for subscription in sheriff_config.subscriptions:
      for pattern in subscription.patterns:
        if pattern.HasField('glob'):
          matcher = re.compile(fnmatch.translate(pattern.glob))
        elif pattern.HasField('regex'):
          matcher = re.compile(pattern.regex)
        else:
          # TODO(dberris): this is the extension point for supporting new
          # matchers; for now we'll skip the new patterns we don't handle yet.
          continue
        result = matcher.match(request.path)
        if result is not None:
          yield (config['config_set'], config['revision'], subscription)
          # We break immediately after the yield, so that we can ignore the rest
          # of the patterns defined for this subscription.
          break
