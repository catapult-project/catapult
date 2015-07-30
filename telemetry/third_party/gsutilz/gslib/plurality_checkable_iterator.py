# -*- coding: utf-8 -*-
# Copyright 2012 Google Inc. All Rights Reserved.
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
"""Iterator wrapper for checking wrapped iterator's emptiness or plurality."""

# TODO: Here and elsewhere (wildcard_iterator, name_expansion), do not reference
# __iter__ directly because it causes the first element to be instantiated.
# Instead, implement __iter__ as a return self and implement the next() function
# which returns (not yields) the values.  This necessitates that in the case
# of the iterator classes, the iterator is used once per class instantiation
# so that next() calls do not collide, but this semantic has been long-assumed
# by the iterator classes for the use of __iter__ anyway.

from __future__ import absolute_import

import sys


class PluralityCheckableIterator(object):
  """Iterator wrapper class.

    Allows you to check whether the wrapped iterator is empty and
    whether it has more than 1 element. This iterator accepts three types of
    values from the iterator it wraps:
      1. A yielded element (this is the normal case).
      2. A raised exception, which will be buffered and re-raised when it
         is reached in this iterator.
      3. A yielded tuple of (exception, stack trace), which will be buffered
         and raised with it is reached in this iterator.
  """

  def __init__(self, it):
    # Need to get the iterator function here so that we don't immediately
    # instantiate the first element (which could raise an exception).
    self.orig_iterator = it
    self.base_iterator = None
    self.head = []
    self.underlying_iter_empty = False
    # Populate first 2 elems into head so we can check whether iterator has
    # more than 1 item.
    for _ in range(0, 2):
      self._PopulateHead()

  def _PopulateHead(self):
    if not self.underlying_iter_empty:
      try:
        if not self.base_iterator:
          self.base_iterator = iter(self.orig_iterator)
        e = self.base_iterator.next()
        self.underlying_iter_empty = False
        if isinstance(e, tuple) and isinstance(e[0], Exception):
          self.head.append(('exception', e[0], e[1]))
        else:
          self.head.append(('element', e))
      except StopIteration:
        # Indicates we can no longer call next() on underlying iterator, but
        # there could still be elements left to iterate in head.
        self.underlying_iter_empty = True
      except Exception, e:
        # Buffer the exception and raise it when the element is accessed.
        # Also, preserve the original stack trace, as the stack trace from
        # within plurality_checkable_iterator.next is not very useful.
        self.head.append(('exception', e, sys.exc_info()[2]))

  def __iter__(self):
    return self

  def next(self):
    # Backfill into head each time we pop an element so we can always check
    # for emptiness and for HasPlurality().
    while self.head:
      self._PopulateHead()
      item_tuple = self.head.pop(0)
      if item_tuple[0] == 'element':
        return item_tuple[1]
      else:  # buffered exception
        raise item_tuple[1].__class__, item_tuple[1], item_tuple[2]
    raise StopIteration()

  def IsEmpty(self):
    return not self.head

  def HasPlurality(self):
    return len(self.head) > 1
