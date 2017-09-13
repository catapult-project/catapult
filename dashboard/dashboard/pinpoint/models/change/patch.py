# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections


class Patch(collections.namedtuple('Patch', ('server', 'issue', 'patchset'))):
  """A patch in Rietveld."""
  # TODO: Support Gerrit.
  # https://github.com/catapult-project/catapult/issues/3599

  def __str__(self):
    return self.id_string

  @property
  def id_string(self):
    return '%s/%d/%d' % (self.server, self.issue, self.patchset)

  def AsDict(self):
    return self._asdict()

  @classmethod
  def FromDict(cls, data):
    # TODO: Validate to ensure the patch exists on the server.
    return cls(data['server'], data['issue'], data['patchset'])
