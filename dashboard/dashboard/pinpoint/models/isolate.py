# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Model for storing information to look up isolates.

An isolate is a way to describe the dependencies of a specific build.

More about isolates:
https://github.com/luci/luci-py/blob/master/appengine/isolate/doc/client/Design.md
"""

from google.appengine.ext import ndb


# A list of builders that recently changed names.
# TODO(dtu): Remove 6 months after LUCI migration is complete.
_BUILDER_NAME_MAP = {
    'Android arm64 Compile Perf': 'android_arm64-builder-perf',
}


def Get(builder_name, change, target):
  """Retrieve an isolate hash from the Datastore.

  Args:
    builder_name: The name of the builder that produced the isolate.
    change: The Change the isolate was built at.
    target: The compile target the isolate is for.

  Returns:
    A tuple containing the isolate server and isolate hash as strings.
  """
  entity = ndb.Key(Isolate, _Key(builder_name, change, target)).get()
  if not entity:
    if builder_name in _BUILDER_NAME_MAP:
      # The builder has changed names. Try again with the new name.
      # TODO(dtu): Remove 6 months after LUCI migration is complete.
      builder_name = _BUILDER_NAME_MAP[builder_name]
      entity = ndb.Key(Isolate, _Key(builder_name, change, target)).get()
      if not entity:
        raise KeyError('No isolate with builder %s, change %s, and target %s.' %
                       (builder_name, change, target))
    else:
      raise KeyError('No isolate with builder %s, change %s, and target %s.' %
                     (builder_name, change, target))
  return entity.isolate_server, entity.isolate_hash


def Put(isolate_infos):
  """Add isolate hashes to the Datastore.

  This function takes multiple entries to do a batched Datstore put.

  Args:
    isolate_infos: An iterable of tuples. Each tuple is of the form
        (builder_name, change, target, isolate_server, isolate_hash).
  """
  entities = []
  for isolate_info in isolate_infos:
    builder_name, change, target, isolate_server, isolate_hash = isolate_info
    entity = Isolate(
        isolate_server=isolate_server,
        isolate_hash=isolate_hash,
        id=_Key(builder_name, change, target))
    entities.append(entity)
  ndb.put_multi(entities)


class Isolate(ndb.Model):
  isolate_server = ndb.StringProperty(indexed=False, required=True)
  isolate_hash = ndb.StringProperty(indexed=False, required=True)
  created = ndb.DateTimeProperty(auto_now_add=True)


def _Key(builder_name, change, target):
  # The key must be stable across machines, platforms,
  # Python versions, and Python invocations.
  return '\n'.join((builder_name, change.id_string, target))
