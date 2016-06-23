# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""GetTraccHandlesQuery is designed to be either evaluable directly
from python, or be convertable to an Appengine datastore query. As a result,
exercise discretion when adding features to this class.
"""
import operator
import re
import datetime


def _InOp(a, b):
  return a in b


class _ReadField(object):

  def __init__(self, fieldName):
    self.fieldName = fieldName

  def AsQueryString(self):
    return self.fieldName

  def Eval(self, metadata):
    return metadata[self.fieldName]


class _Constant(object):

  def __init__(self, constant):
    self.constant = constant

  def AsQueryString(self):
    if isinstance(self.constant, list):
      # Tuples
      return '(%s)' % ','.join([c.AsQueryString() for c in self.constant])
    elif isinstance(self.constant, (datetime.datetime, datetime.date)):
      # Dates.
      return self.constant.strftime("Date(%Y-%m-%d %H:%M:%S.%f)")
    elif isinstance(self.constant, str):
      # Strings need quotes.
      return "'%s'" % self.constant
    # Everything else from the eval() statement below.
    return str(self.constant)

  def Eval(self, metadata):
    # pylint: disable=unused-argument
    return self.constant


def _StringToValue(s):
  try:
    constant = eval(s, {}, {})
    return _Constant(constant)
  except Exception:  # pylint: disable=bare-except
    pass

  # Barewords are assumed to be fields.
  m = re.match(r'([a-zA-Z0-9_]+)$', s)
  if m:
    return _ReadField(m.group(1))

  # Tuples.
  m = re.match(r'\(.+\)$', s)
  if m:
    items = m.group(0).split(r',\s*')
    return _Constant([_StringToValue(x) for x in items])

  # Dates.
  m = re.match(r'Date\((.+)\)$', s)
  if m:
    d = datetime.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S.%f")
    return _Constant(d)

  # Dunno!
  raise NotImplementedError()

_OPERATORS = {
  '=': operator.eq,
  '<': operator.lt,
  '<=': operator.le,
  '>': operator.gt,
  '>=': operator.ge,
  '!=': operator.ne,
  ' IN ': _InOp  # Spaces matter for proper parsing.
}


def _OperatorToString(op):
  for k, v in _OPERATORS.iteritems():
    if op == v:
      return k
  raise NotImplementedError()


# Since we use find(token) in our actual tokenizing function,
# we need to search for the longest tokens first so that '<=' is searched
# for first, bofore '<', for instance.
_TOKEN_SEARCH_ORDER = list(_OPERATORS.keys())
_TOKEN_SEARCH_ORDER.sort(lambda x, y: len(y) - len(x))


class Filter(object):

  def __init__(self, a, op, b):
    self.a = a
    self.op = op
    self.b = b

  def Eval(self, metadata):
    return self.op(self.a.Eval(metadata),
                   self.b.Eval(metadata))

  def AsQueryString(self):
    # strip() the operator in case we get " IN ", just so that it's not
    # double spaced.
    return '%s %s %s' % (self.a.AsQueryString(),
                         _OperatorToString(self.op).strip(),
                         self.b.AsQueryString())

  @staticmethod
  def FromString(s):
    found_op_key = None
    found_op_key_idx = -1
    for op_key in _TOKEN_SEARCH_ORDER:
      i = s.find(op_key)
      if i != -1:
        found_op_key_idx = i
        found_op_key = op_key
        break

    if found_op_key_idx == -1:
      raise Exception('Expected: operator')

    lvalue = s[:found_op_key_idx]
    rvalue = s[found_op_key_idx + len(found_op_key):]

    lvalue = lvalue.strip()
    rvalue = rvalue.strip()

    lvalue = _StringToValue(lvalue)
    rvalue = _StringToValue(rvalue)

    if not isinstance(lvalue, _ReadField) or not isinstance(rvalue, _Constant):
      # GQL Syntax needs the property on the left and the value on the right.
      # https://cloud.google.com/appengine/docs/python/datastore/gqlreference
      raise Exception('Expected lvalue field and rvalue constant')

    return Filter(lvalue,
                  _OPERATORS[found_op_key],
                  rvalue)


class CorpusQuery(object):

  def __init__(self):
    self.max_trace_handles = None
    self.filters = []

  def AsGQLWhereClause(self):
    gql = ''
    args = []
    if self.filters:
      filter_strings = []
      for f in self.filters:
        # Constants need to be passed back as positional arguments to avoid
        # potential gql injection problems.
        a_string = ''
        if isinstance(f.a, _Constant):
          args.append(f.a.constant)
          a_string = ':%d' % len(args)
        else:
          a_string = f.a.fieldName

        b_string = ''
        if isinstance(f.b, _Constant):
          args.append(f.b.constant)
          b_string = ':%d' % len(args)
        else:
          b_string = f.b.fieldName

        filter_strings.append('%s %s %s' % (a_string,
                                             _OperatorToString(f.op).strip(),
                                             b_string))
      gql = 'WHERE ' + ' AND '.join(filter_strings)
    if self.max_trace_handles:
      gql += ' LIMIT %d' % self.max_trace_handles
    # strip() the final GQL in case it's just " LIMIT 1", just so that it looks
    # a bit nicer.
    return (gql.strip(), args)

  def AsQueryString(self):
    filter_strings = [f.AsQueryString() for f in self.filters]
    if self.max_trace_handles:
      filter_strings.append('MAX_TRACE_HANDLES=%d' % self.max_trace_handles)
    query_str = ' AND '.join(filter_strings)
    return query_str

  @staticmethod
  def FromString(filterString):
    """This follows the same filter rules as GQL"""
    if filterString == 'True' or filterString == '':
      return CorpusQuery()

    q = CorpusQuery()
    exprs = filterString.split(' AND ')
    for expr in exprs:
      m = re.match(r'MAX_TRACE_HANDLES\s*=\s*(\d+)', expr)
      if m:
        q.max_trace_handles = int(m.group(1))
        continue

      f = Filter.FromString(expr)
      q.filters.append(f)

    return q

  def Eval(self, metadata, num_trace_handles_so_far=0):
    if not self.max_trace_handles is None:
      if num_trace_handles_so_far >= self.max_trace_handles:
        return False

    for flt in self.filters:
      if not flt.Eval(metadata):
        return False

    return True
