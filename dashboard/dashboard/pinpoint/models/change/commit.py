# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections

from dashboard.pinpoint.models.change import repository as repository_module
from dashboard.services import gitiles_service


class NonLinearError(Exception):
  """Raised when trying to find the midpoint of Changes that are not linear."""


class Commit(collections.namedtuple('Commit', ('repository', 'git_hash'))):
  """A git repository pinned to a particular commit."""

  def __str__(self):
    """Returns an informal short string representation of this Commit."""
    return self.repository + '@' + self.git_hash[:7]

  @property
  def id_string(self):
    """Returns a string that is unique to this repository and git hash."""
    return self.repository + '@' + self.git_hash

  @property
  def repository_url(self):
    """The HTTPS URL of the repository as passed to `git clone`."""
    return repository_module.RepositoryUrl(self.repository)

  def Details(self):
    """The details of this Commit, including author and message, as a dict.

    Returns:
      A dictionary containing the author, message, time, file changes, and other
      information. See services/gitiles_service_test.py for an example.
    """
    # TODO: Store the commit info in the datastore and make this a property.
    return gitiles_service.CommitInfo(self.repository_url, self.git_hash)

  def Deps(self):
    """Return the DEPS of this Commit as a frozenset of Commits."""
    # Download and execute DEPS file.
    try:
      deps_file_contents = gitiles_service.FileContents(
          self.repository_url, self.git_hash, 'DEPS')
    except gitiles_service.NotFoundError:
      return frozenset()  # No DEPS file => no DEPS.

    deps_data = {'Var': lambda variable: deps_data['vars'][variable]}
    exec deps_file_contents in deps_data  # pylint: disable=exec-used

    # Pull out deps dict, including OS-specific deps.
    deps_dict = deps_data['deps']
    for deps_os in deps_data.get('deps_os', {}).itervalues():
      deps_dict.update(deps_os)

    # Convert deps strings to Commit objects.
    commits = []
    for dep_value in deps_dict.itervalues():
      if isinstance(dep_value, basestring):
        dep_string = dep_value
      else:
        dep_string = dep_value['url']

      dep_string_parts = dep_string.split('@')
      if len(dep_string_parts) < 2:
        continue  # Dep is not pinned to any particular revision.
      if len(dep_string_parts) > 2:
        raise NotImplementedError('Unknown DEP format: ' + dep_string)

      repository_url, git_hash = dep_string_parts
      repository = repository_module.Repository(repository_url,
                                                add_if_missing=True)
      commits.append(Commit(repository, git_hash))

    return frozenset(commits)

  def AsDict(self):
    return {
        'repository': self.repository,
        'git_hash': self.git_hash,
        'url': self.repository_url + '/+/' + self.git_hash,
    }

  @classmethod
  def FromDict(cls, data):
    """Create a Commit from a dict.

    If the repository is a repository URL, it will be translated to its short
    form name.

    Raises:
      KeyError: The repository name is not in the local datastore,
                or the git hash is not valid.
    """
    repository = data['repository']

    # Translate repository if it's a URL.
    if repository.startswith('https://'):
      repository = repository_module.Repository(repository)

    git_hash = data['git_hash']

    try:
      # If they send in something like HEAD, resolve to a hash.
      repository_url = repository_module.RepositoryUrl(repository)
      result = gitiles_service.CommitInfo(repository_url, git_hash)
      git_hash = result['commit']
    except gitiles_service.NotFoundError as e:
      raise KeyError(str(e))

    commit = cls(repository, git_hash)

    return commit

  @classmethod
  def Midpoint(cls, commit_a, commit_b):
    """Return a Commit halfway between the two given Commits.

    Uses Gitiles to look up the commit range.

    Args:
      commit_a: The first Commit in the range.
      commit_b: The last Commit in the range.

    Returns:
      A new Commit representing the midpoint.
      The commit before the midpoint if the range has an even number of commits.
      commit_a if the Commits are the same or adjacent.

    Raises:
      NonLinearError: The Commits are in different repositories or commit_a does
        not come before commit_b.
    """
    if commit_a == commit_b:
      return commit_a

    if commit_a.repository != commit_b.repository:
      raise NonLinearError('Repositories differ between Commits: %s vs %s' %
                           (commit_a.repository, commit_b.repository))

    commits = gitiles_service.CommitRange(commit_a.repository_url,
                                          commit_a.git_hash, commit_b.git_hash)
    # We don't handle NotFoundErrors because we assume that all Commits either
    # came from this method or were already validated elsewhere.
    if len(commits) == 0:
      raise NonLinearError('Commit "%s" does not come before commit "%s".' %
                           commit_a, commit_b)
    if len(commits) == 1:
      return commit_a
    commits.pop(0)  # Remove commit_b from the range.

    return cls(commit_a.repository, commits[len(commits) / 2]['commit'])
