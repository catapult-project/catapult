# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections

from soundwave import utils


_Bug = collections.namedtuple('Bug', [
    'id', 'summary', 'published', 'updated', 'state', 'status',
    'author', 'owner', 'cc', 'components', 'labels'])


def _CommaSeparate(values):
  assert isinstance(values, list)
  if values:
    return ','.join(values)
  else:
    return None


class Bug(_Bug):
  __slots__ = ()
  name = 'bugs'
  columns = _Bug._fields

  @classmethod
  def FromTuple(cls, row):
    return cls._make(row)

  @classmethod
  def FromJson(cls, data):
    kwargs = {k: data[k] for k in cls.columns if k in data}
    kwargs['published'] = utils.IsoFormatStrToTimestamp(data['published'])
    kwargs['updated'] = utils.IsoFormatStrToTimestamp(data['updated'])
    kwargs['cc'] = _CommaSeparate(data['cc'])
    kwargs['components'] = _CommaSeparate(data['components'])
    kwargs['labels'] = _CommaSeparate(data['labels'])
    return cls(**kwargs)
