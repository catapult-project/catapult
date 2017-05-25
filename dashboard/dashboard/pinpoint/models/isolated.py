# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Model for storing information to look up .isolated files.

An .isolated file is a way to describe the dependencies of a specific build.

More about isolates:
https://github.com/luci/luci-py/blob/master/appengine/isolate/doc/client/Design.md
"""

from google.appengine.ext import ndb


def Get(builder_name, change, target):
  """Retrieve an isolated hash from the Datastore.

  Args:
    builder_name: The name of the builder that produced the isolated.
    change: The Change the isolated was built at.
    target: The compile target the isolated is for.

  Returns:
    The isolated hash as a string.
  """
  key = ndb.Key(Isolated, _Key(builder_name, change, target))
  entity = key.get()
  if not entity:
    raise KeyError('No isolated with builder %s, change %s, and target %s.' %
                   (builder_name, change, target))
  return entity.isolated_hash


def Put(isolated_infos):
  """Add isolated hashes to the Datastore.

  This function takes multiple entries to do a batched Datstore put.

  Args:
    isolated_infos: An iterable of tuples. Each tuple is of the form
        (builder_name, change, target, isolated_hash).
  """
  entities = []
  for isolated_info in isolated_infos:
    builder_name, change, target, isolated_hash = isolated_info
    entity = Isolated(
        builder_name=builder_name,
        change=change,
        target=target,
        isolated_hash=isolated_hash,
        id=_Key(builder_name, change, target))
    entities.append(entity)
  ndb.put_multi(entities)


class Isolated(ndb.Model):
  builder_name = ndb.StringProperty(required=True)
  change = ndb.PickleProperty(required=True)
  target = ndb.StringProperty(required=True)
  isolated_hash = ndb.StringProperty(required=True)


def _Key(builder_name, change, target):
  return hex(hash((builder_name, change, target)))
