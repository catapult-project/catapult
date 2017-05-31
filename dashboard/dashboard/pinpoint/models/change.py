# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections

from dashboard.common import namespaced_stored_object
from dashboard.services import gitiles_service


_REPOSITORIES_KEY = 'repositories'


class NonLinearError(Exception):
  """Raised when trying to find the midpoint of Changes that are not linear."""


class Change(collections.namedtuple('Change',
                                    ('base_commit', 'deps', 'patch'))):
  """A particular set of Deps with or without an additional patch applied.

  For example, a Change might sync to src@9064a40 and catapult@8f26966,
  then apply patch 2423293002.
  """

  def __new__(cls, base_commit, deps=frozenset(), patch=None):
    """Create a Change.

    Args:
      base_commit: A Dep representing the initial commit to sync to. The DEPS
          file at that commit implies the default commits for any dependencies.
      deps: An optional iterable of Deps to override the dependencies implied
          by base_commit.
      patch: An optional Patch to apply to the Change.
    """
    return super(Change, cls).__new__(cls, base_commit, frozenset(deps), patch)

  def __str__(self):
    string = ' '.join(str(dep) for dep in self.all_deps)
    if self.patch:
      string += ' + ' + str(self.patch)
    return string

  @property
  def all_deps(self):
    return tuple([self.base_commit] + sorted(self.deps))

  @classmethod
  def FromDict(cls, data):
    base_commit = Dep.FromDict(data['base_commit'])

    kwargs = {}
    if 'deps' in data:
      kwargs['deps'] = tuple(Dep.FromDict(dep) for dep in data['deps'])
    if 'patch' in data:
      kwargs['patch'] = Patch.FromDict(data['patch'])

    return cls(base_commit, **kwargs)

  @classmethod
  def Midpoint(cls, change_a, change_b):
    """Return a Change halfway between the two given Changes.

    A NonLinearError is raised if the Changes are not linear. The Changes are
    linear iff they are identical except for exactly one git hash. See
    change_test.py for examples of linear and nonlinear Changes.

    Args:
      change_a: The first Change in the range.
      change_b: The last Change in the range.

    Returns:
      A new Change representing the midpoint.
      The commit before the midpoint if the range has an even number of commits.
      None if the range is empty, or the Changes are given in the wrong order.

    Raises:
      NonLinearError: The Changes are not linear.
    """
    # TODO: Handle DEPS rolls, including nested ones.
    _ValidateChangeLinearity(change_a, change_b)

    midpoint_all_deps = []
    for dep_a, dep_b in zip(change_a.all_deps, change_b.all_deps):
      if dep_a.git_hash == dep_b.git_hash:
        midpoint_dep = dep_a
      else:
        midpoint_dep = Dep.Midpoint(dep_a, dep_b)
        if not midpoint_dep:
          return None

      midpoint_all_deps.append(midpoint_dep)

    return cls(midpoint_all_deps[0], midpoint_all_deps[1:], change_a.patch)


class Dep(collections.namedtuple('Dep', ('repository', 'git_hash'))):
  """A git repository pinned to a particular commit."""

  def __str__(self):
    return self.repository + '@' + self.git_hash[:7]

  @property
  def repository_url(self):
    """The HTTPS URL of the repository as passed to `git clone`."""
    repositories = namespaced_stored_object.Get(_REPOSITORIES_KEY)
    return repositories[self.repository]['repository_url']

  def Validate(self):
    """Validate the Dep to ensure it has a valid repository and git hash.

    Raises:
      KeyError: The repository name is not in the local datastore.
      gitiles_service.NotFoundError: The git hash is not valid.
    """
    gitiles_service.CommitInfo(self.repository_url, self.git_hash)

  @classmethod
  def FromDict(cls, data):
    return cls(data['repository'], data['git_hash'])

  @classmethod
  def Midpoint(cls, dep_a, dep_b):
    """Return a Dep halfway between the two given Deps.

    Uses Gitiles to look up the commit range.

    Args:
      dep_a: The first Dep in the range.
      dep_b: The last Dep in the range.

    Returns:
      A new Dep representing the midpoint.
      The commit before the midpoint if the range has an even number of commits.
      None if the range is empty, or the Deps are given in the wrong order.

    Raises:
      ValueError: The Deps are in different repositories.
    """
    if dep_a.repository != dep_b.repository:
      raise ValueError("Can't find the midpoint of Deps in differing "
                       'repositories: "%s" and "%s"' % (dep_a, dep_b))

    commits = gitiles_service.CommitRange(dep_a.repository_url,
                                          dep_a.git_hash, dep_b.git_hash)
    # We don't handle NotFoundErrors because we assume that all Deps either came
    # from this method or were already validated elsewhere.
    if len(commits) <= 1:
      return None
    commits = commits[1:]  # Remove dep_b from the range.

    return cls(dep_a.repository, commits[len(commits) / 2]['commit'])


class Patch(collections.namedtuple('Patch', ('server', 'issue', 'patchset'))):
  """A patch in Rietveld."""
  # TODO: Support Gerrit.
  # https://github.com/catapult-project/catapult/issues/3599

  def __str__(self):
    return '%s/%d/%d' % (self.server, self.issue, self.patchset)

  @classmethod
  def FromDict(cls, data):
    return cls(data['server'], data['issue'], data['patchset'])


def _ValidateChangeLinearity(change_a, change_b):
  if len(change_a.deps) != len(change_b.deps):
    raise NonLinearError('Change A has %d deps and Change B has %d deps' %
                         (len(change_a.deps), len(change_b.deps)))

  if change_a.patch != change_b.patch:
    raise NonLinearError('Change A has patch "%s" and Change B has patch "%s"'
                         % (change_a.patch, change_b.patch))

  differences = 0
  for dep_a, dep_b in zip(change_a.all_deps, change_b.all_deps):
    if dep_a.repository != dep_b.repository:
      raise NonLinearError('Change A has repository "%s" and '
                           'Change B has repository "%s"' %
                           (dep_a.repository, dep_b.repository))

    if dep_a.git_hash != dep_b.git_hash:
      differences += 1

  if differences == 0:
    raise NonLinearError('The Changes are the same.')
  elif differences > 1:
    raise NonLinearError('The Changes have multiple differing commits.')
