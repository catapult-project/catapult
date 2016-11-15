# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class Change(object):
  """A particular set of Deps with or without an additional patch applied.

  For example, a Change might sync to chromium/src@9064a40 and catapult@8f26966,
  then apply patch 2423293002.
  """

  def __init__(self, base_commit, deps=(), patch=None):
    self._base_commit = base_commit
    self._deps = tuple(deps)
    self._patch = patch


class Dep(object):
  """A git repository pinned to a particular commit."""

  def __init__(self, repository, git_hash):
    self._repository = repository
    self._git_hash = git_hash
