# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""The datastore model TableConfig, which specify which reports to generate.

Each /speed_releasing report will be generated via creating a corresponding
configuration which lists which bots and tests the user is interested in,
as well as a user friendly name and the actual table layout.

Example input for bots:
["ChromiumPerf/Nexus5", "ClankInternal/mako"]

Example input for tests:
["memory.top_10_mobile/memory:chrome:all_processes:reported_by_os:system_memory:
ashmem:proportional_resident_size_avg",
memory.top_10_mobile/memory:chrome:all_processes:reported_by_os:system_memory:
java_heap:proportional_resident_size_avg"]

Example input for test_layout:
{
  "system_health.memory_mobile/foreground/ashmem": ["Foreground", "Ashmem"]
  ...
}
Here, we have the test_path: [Category, Name]. This is useful for formatting
the table. We can split each test into different categories and rename the tests
to something more useful for the user.

"""
import json

from google.appengine.ext import ndb

from dashboard.models import internal_only_model


class TableConfig(internal_only_model.InternalOnlyModel):

  # A list of bots the speed releasing report will contain.
  bots = ndb.KeyProperty(repeated=True)

  # A list of testsuites/subtests that each speed releasing report will contain.
  tests = ndb.StringProperty(repeated=True)

  # Aids in displaying the table by showing groupings and giving pretty names.
  table_layout = ndb.JsonProperty()

  internal_only = ndb.BooleanProperty(default=False, indexed=True)

  # The username of the creator
  username = ndb.StringProperty()

def CreateTableConfig(name, bots, tests, layout, username):
  """Performs checks to verify bots and layout are valid, sets internal_only.

  Args:
    name: User friendly name for the report.
    bots: List of master/bot pairs.
    tests: List of test paths.
    layout: JSON serializable layout for the table.
    username: Email address of user creating the report.

  Returns:
    The created table_config and a success. If nothing is created (because
    of bad inputs), returns None, error message.
  """
  internal_only = False
  error_message = ''
  valid_bots = []
  for bot in bots:
    if '/' in bot:
      bot_name = bot.split('/')[1]
      master_name = bot.split('/')[0]
      entity_key = ndb.Key('Master', master_name, 'Bot', bot_name)
      entity = entity_key.get()
      if entity:
        valid_bots.append(entity_key)
        if entity.internal_only:
          internal_only = True
      else:
        error_message = 'Invalid Master/Bot: %s' % bot
        return None, error_message
    else:
      error_message = 'Invalid Master/Bot: %s' % bot
      return None, error_message

  try:
    json.loads(layout)
    # TODO(jessimb): Verify that the layout matches what is expected
  except ValueError:
    error_message = 'Invalid JSON for table layout'
    return None, error_message

  table_check = ndb.Key('TableConfig', name).get()
  if table_check:
    error_message = '%s already exists.' % name
    return None, error_message

  # Input validates, create table now.
  error_message = 'TableConfig created successfully.'
  table_config = TableConfig(id=name, bots=valid_bots, tests=tests,
                             table_layout=layout, internal_only=internal_only,
                             username=username)
  table_config.put()
  return table_config, error_message

