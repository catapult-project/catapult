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

  @property
  def base_commit(self):
    return self._base_commit

  @property
  def deps(self):
    return self._deps

  @property
  def patch(self):
    return self._patch

  @property
  def most_specific_commit(self):
    return self._deps[-1] if self._deps else self._base_commit


class Dep(object):
  """A git repository pinned to a particular commit."""

  def __init__(self, repository, git_hash):
    self._repository = repository
    self._git_hash = git_hash

  @property
  def repository(self):
    return self._repository

  @property
  def git_hash(self):
    return self._git_hash
