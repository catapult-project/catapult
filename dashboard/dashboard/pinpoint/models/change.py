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
    not linear if any of the following is true:
      * They have different base repositories.
      * They have different patches.
      * Their repositories differ even after expanding DEPS rolls.
    See change_test.py for examples of linear and nonlinear Changes.

    The behavior is undefined if either of the Changes have multiple Deps with
    the same repository.

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
    if change_a.base_commit.repository != change_b.base_commit.repository:
      raise NonLinearError(
          'Change A has base repo "%s" and Change B has base repo "%s".' %
          (change_a.base_commit.repository, change_b.base_commit.repository))

    if change_a.patch != change_b.patch:
      raise NonLinearError(
          'Change A has patch "%s" and Change B has patch "%s".' %
          (change_a.patch, change_b.patch))

    if change_a == change_b:
      return None

    # Find the midpoint of every pair of Deps, expanding DEPS rolls as we go.
    midpoint_deps = {}

    repositories_a = {dep.repository: dep for dep in change_a.all_deps}
    repositories_b = {dep.repository: dep for dep in change_b.all_deps}

    # Match up all the Deps by repository.
    while frozenset(repositories_a.iterkeys()).intersection(
        frozenset(repositories_b.iterkeys())):
      # Choose an arbitrary pair of Deps with the same repository.
      shared_repositories = set(repositories_a.iterkeys()).intersection(
          set(repositories_b.iterkeys()))
      repository = shared_repositories.pop()
      dep_a = repositories_a.pop(repository)
      dep_b = repositories_b.pop(repository)

      if dep_a == dep_b:
        # The Deps are the same.
        midpoint_deps[repository] = dep_a
        continue

      midpoint_dep = Dep.Midpoint(dep_a, dep_b)
      if midpoint_dep:
        # The Deps are not adjacent.
        midpoint_deps[repository] = midpoint_dep
        continue

      # The Deps are adjacent. Figure out if it's a DEPS roll.
      deps_a = dep_a.Deps()
      deps_b = dep_b.Deps()
      if deps_a == deps_b:
        # Not a DEPS roll. The Changes really are adjacent.
        return None

      # DEPS roll! Expand the roll.
      for dep in deps_a.difference(deps_b):
        if dep.repository in midpoint_deps:
          raise NonLinearError('Tried to take the midpoint across a DEPS roll, '
                               'but the underlying Dep is already overriden in '
                               'both Changes.')
        if dep.repository not in repositories_a:
          repositories_a[dep.repository] = dep
      for dep in deps_b.difference(deps_a):
        if dep.repository in midpoint_deps:
          raise NonLinearError('Tried to take the midpoint across a DEPS roll, '
                               'but the underlying Dep is already overriden in '
                               'both Changes.')
        if dep.repository not in repositories_b:
          repositories_b[dep.repository] = dep
      midpoint_deps[repository] = dep_a

    # Now that the DEPS are expanded, check to see if the repositories differ.
    if repositories_a or repositories_b:
      raise NonLinearError(
          'Repositories differ between Change A and Change B: %s' %
          ', '.join(sorted(repositories_a.keys() + repositories_b.keys())))

    # Create our new Change!
    base_commit = midpoint_deps.pop(change_a.base_commit.repository)
    return cls(base_commit, midpoint_deps.itervalues(), change_a.patch)


class Dep(collections.namedtuple('Dep', ('repository', 'git_hash'))):
  """A git repository pinned to a particular commit."""

  def __str__(self):
    return self.repository + '@' + self.git_hash[:7]

  @property
  def repository_url(self):
    """The HTTPS URL of the repository as passed to `git clone`."""
    repositories = namespaced_stored_object.Get(_REPOSITORIES_KEY)
    return repositories[self.repository]['repository_url']

  def Deps(self):
    """Return the DEPS of this Dep as a frozenset of Deps."""
    # Download and execute DEPS file.
    deps_file_contents = gitiles_service.FileContents(
        self.repository_url, self.git_hash, 'DEPS')
    deps_data = {'Var': lambda variable: deps_data['vars'][variable]}
    exec deps_file_contents in deps_data  # pylint: disable=exec-used

    # Pull out deps dict, including OS-specific deps.
    deps_dict = deps_data['deps']
    for deps_os in deps_data.get('deps_os', {}).itervalues():
      deps_dict.update(deps_os)

    # Convert deps strings to Dep objects.
    deps = []
    for dep_string in deps_dict.itervalues():
      dep_string_parts = dep_string.split('@')
      if len(dep_string_parts) < 2:
        continue  # Dep is not pinned to any particular revision.
      if len(dep_string_parts) > 2:
        raise NotImplementedError('Unknown DEP format: ' + dep_string)

      repository_url, git_hash = dep_string_parts
      repository = _Repository(repository_url)
      if not repository:
        _AddRepository(repository_url)
        repository = _Repository(repository_url)
      deps.append(Dep(repository, git_hash))

    return frozenset(deps)

  @classmethod
  def FromDict(cls, data):
    """Create a Dep from a dict.

    If the repository is a repository URL, it will be translated to its short
    form name.

    Raises:
      KeyError: The repository name is not in the local datastore,
                or the git hash is not valid.
    """
    repository = data['repository']

    # Translate repository if it's a URL.
    repository_from_url = _Repository(repository)
    if repository_from_url:
      repository = repository_from_url

    dep = cls(repository, data['git_hash'])

    try:
      gitiles_service.CommitInfo(dep.repository_url, dep.git_hash)
    except gitiles_service.NotFoundError as e:
      raise KeyError(e)

    return dep

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
    # TODO: Validate to ensure the patch exists on the server.
    return cls(data['server'], data['issue'], data['patchset'])


def _Repository(repository_url):
  repositories = namespaced_stored_object.Get(_REPOSITORIES_KEY)
  for repo_label, repo_info in repositories.iteritems():
    if repository_url == repo_info['repository_url']:
      return repo_label

  return None


def _AddRepository(repository_url):
  repositories = namespaced_stored_object.Get(_REPOSITORIES_KEY)
  repository = repository_url.split('/')[-1]
  if repository.endswith('.git'):
    repository = repository[:-4]

  if repository in repositories:
    raise AssertionError("Attempted to add a repository that's already in the "
                         'Datastore: %s: %s' % (repository, repository_url))

  repositories[repository] = {'repository_url': repository_url}
  namespaced_stored_object.Set(_REPOSITORIES_KEY, repositories)
