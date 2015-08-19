# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A wrapper for stored_object that separates internal and external."""

from dashboard import datastore_hooks
from dashboard import stored_object


def Get(key):
  """Gets either the external or internal copy of an object."""
  namespaced_key = _NamespaceKey(key)
  return stored_object.Get(namespaced_key)


def GetExternal(key):
  """Gets the external copy of a stored object."""
  namespaced_key = _NamespaceKey(key, datastore_hooks.EXTERNAL)
  return stored_object.Get(namespaced_key)


def Set(key, value):
  """Sets the the value of a stored object, either external or internal."""
  namespaced_key = _NamespaceKey(key)
  stored_object.Set(namespaced_key, value)


def SetExternal(key, value):
  """Sets the external copy of a stored object."""
  namespaced_key = _NamespaceKey(key, datastore_hooks.EXTERNAL)
  stored_object.Set(namespaced_key, value)


def Delete(key):
  """Deletes both the internal and external copy of a stored object."""
  internal_key = _NamespaceKey(key, namespace=datastore_hooks.INTERNAL)
  external_key = _NamespaceKey(key, namespace=datastore_hooks.EXTERNAL)
  stored_object.Delete(internal_key)
  stored_object.Delete(external_key)


def _NamespaceKey(key, namespace=None):
  """Prepends a namespace string to a key string."""
  if not namespace:
    namespace = datastore_hooks.GetNamespace()
  return '%s__%s' % (namespace, key)
