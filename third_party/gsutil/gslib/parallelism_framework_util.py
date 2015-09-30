# -*- coding: utf-8 -*-
# Copyright 2013 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Utility classes for the parallelism framework."""

from __future__ import absolute_import

import multiprocessing
import threading


class BasicIncrementDict(object):
  """Dictionary meant for storing values for which increment is defined.

  This handles any values for which the "+" operation is defined (e.g., floats,
  lists, etc.). This class is neither thread- nor process-safe.
  """

  def __init__(self):
    self.dict = {}

  def Get(self, key, default_value=None):
    return self.dict.get(key, default_value)

  def Put(self, key, value):
    self.dict[key] = value

  def Update(self, key, inc, default_value=0):
    """Update the stored value associated with the given key.

    Performs the equivalent of
    self.put(key, self.get(key, default_value) + inc).

    Args:
      key: lookup key for the value of the first operand of the "+" operation.
      inc: Second operand of the "+" operation.
      default_value: Default value if there is no existing value for the key.

    Returns:
      Incremented value.
    """
    val = self.dict.get(key, default_value) + inc
    self.dict[key] = val
    return val


class AtomicIncrementDict(BasicIncrementDict):
  """Dictionary meant for storing values for which increment is defined.

  This handles any values for which the "+" operation is defined (e.g., floats,
  lists, etc.) in a thread- and process-safe way that allows for atomic get,
  put, and update.
  """

  def __init__(self, manager):  # pylint: disable=super-init-not-called
    self.dict = ThreadAndProcessSafeDict(manager)
    self.lock = multiprocessing.Lock()

  def Update(self, key, inc, default_value=0):
    """Atomically update the stored value associated with the given key.

    Performs the atomic equivalent of
    self.put(key, self.get(key, default_value) + inc).

    Args:
      key: lookup key for the value of the first operand of the "+" operation.
      inc: Second operand of the "+" operation.
      default_value: Default value if there is no existing value for the key.

    Returns:
      Incremented value.
    """
    with self.lock:
      return super(AtomicIncrementDict, self).Update(key, inc, default_value)


class ThreadSafeDict(object):
  """Provides a thread-safe dictionary (protected by a lock)."""

  def __init__(self):
    """Initializes the thread-safe dict."""
    self.lock = threading.Lock()
    self.dict = {}

  def __getitem__(self, key):
    with self.lock:
      return self.dict[key]

  def __setitem__(self, key, value):
    with self.lock:
      self.dict[key] = value

  # pylint: disable=invalid-name
  def get(self, key, default_value=None):
    with self.lock:
      return self.dict.get(key, default_value)

  def delete(self, key):
    with self.lock:
      del self.dict[key]


class ThreadAndProcessSafeDict(ThreadSafeDict):
  """Wraps a multiprocessing.Manager's proxy objects for thread-safety.

  The proxy objects returned by a manager are process-safe but not necessarily
  thread-safe, so this class simply wraps their access with a lock for ease of
  use. Since the objects are process-safe, we can use the more efficient
  threading Lock.
  """

  def __init__(self, manager):
    """Initializes the thread and process safe dict.

    Args:
      manager: Multiprocessing.manager object.
    """
    super(ThreadAndProcessSafeDict, self).__init__()
    self.dict = manager.dict()
