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

import threading


class AtomicDict(object):
  """Thread-safe (and optionally process-safe) dictionary protected by a lock.

  If a multiprocessing.Manager is supplied on init, the dictionary is
  both process and thread safe. Otherwise, it is only thread-safe.
  """

  def __init__(self, manager=None):
    """Initializes the dict.

    Args:
      manager: multiprocessing.Manager instance (required for process safety).
    """
    if manager:
      self.lock = manager.Lock()
      self.dict = manager.dict()
    else:
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

  def Increment(self, key, inc, default_value=0):
    """Atomically updates the stored value associated with the given key.

    Performs the atomic equivalent of
    dict[key] = dict.get(key, default_value) + inc.

    Args:
      key: lookup key for the value of the first operand of the "+" operation.
      inc: Second operand of the "+" operation.
      default_value: Default value if there is no existing value for the key.

    Returns:
      Incremented value.
    """
    with self.lock:
      val = self.dict.get(key, default_value) + inc
      self.dict[key] = val
      return val
