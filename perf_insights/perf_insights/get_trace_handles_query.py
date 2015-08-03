# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import operator
import re

"""
GetTraccHandlesQuery is designed to be either evaluable directly
from python, or be convertable to an Appengine datastore query. As a result,
exercise discretion when adding features to this class.
"""

def _InOp(a, b):
  return a in b

def _StringToValue(s):
  constant = None
  try:
    constant = eval(s, {}, {})
    return constant
  except:
    pass

  m = re.match('(.+)', constant_str)
  if m:
    items = m.group(0).split(',\s*')
    return [_StringToValue(x) for x in items]

  # Maybe date?
  raise NotImplemented()

class Filter(object):
  def __init__(self, field, op, constant):
    op_methods = {
      '=': operator.eq,
      '<': operator.lt,
      '<=': operator.le,
      '>':  operator.gt,
      '>=': operator.ge,
      '!=': operator.ne,
      'IN': _InOp
    }
    self.op = op_methods[op]
    self.field = field
    self.constant = constant

  def Eval(self, datum):
    a = datum.get(self.field, None)
    b = self.constant
    return self.op(a, b)

  @staticmethod
  def FromString(s):
    m = re.match('(\w+?)\s+(..?)\s+(.+)', s)
    if not m:
      raise Exception('Wat')
    constant = _StringToValue(m.group(3))
    return Filter(m.group(1), m.group(2), constant)

class GetTraceHandlesQuery(object):
  def __init__(self, filters=None):
    if filters is None:
      self.filters = []
    else:
        self.filters = filters

  @staticmethod
  def FromString(filterString):
    """This follows the same filter rules as GQL"""
    if filterString == 'True' or filterString == '':
      return GetTraceHandlesQuery()
    filter_strings = filterString.split(' AND ')
    filters = [Filter.FromString(s) for s in filter_strings]
    return GetTraceHandlesQuery(filters)

  def IsMetadataInteresting(self, metadata):
    for flt in self.filters:
      if not flt.Eval(metadata):
        return False
    return True