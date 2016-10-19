# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Functions for getting commit information from Gitiles."""

import base64
import json

from google.appengine.api import urlfetch


_BASE_URL = 'https://chromium.googlesource.com'
_PADDING = ")]}'\n"  # Gitiles padding.


def CommitInfo(repository, git_hash):
  """Fetches information about a commit.

  Args:
    repository: The git repository.
    git_hash: The git hash of the commit.

  Returns:
    A dictionary containing the author, message, time, file changes, and other
    information. See gitiles_service_test.py for an example.
  """
  # TODO: Update the docstrings in this file.
  url = '%s/%s/+/%s?format=JSON' % (_BASE_URL, repository, git_hash)
  return _RequestJson(url)


def CommitRange(repository, first_git_hash, last_git_hash):
  """Fetches the commits in between first and last, including the latter.

  Args:
    repository: The git repository.
    first_git_hash: The git hash of the earliest commit in the range.
    last_git_hash: The git hash of the latest commit in the range.

  Returns:
    A list of dictionaries, one for each commit after the first commit up to
    and including the last commit. For each commit, its dictionary will
    contain information about the author and the comitter and the commit itself.
    See gitiles_service_test.py for an example. The list is in ascending order.
  """
  commits = []
  while last_git_hash:
    url = '%s/%s/+log/%s..%s?format=JSON' % (
        _BASE_URL, repository, first_git_hash, last_git_hash)
    response = _RequestJson(url)
    commits += response['log']
    last_git_hash = response.get('next')
  return commits


def FileContents(repository, git_hash, path):
  """Fetches the contents of a file at a particular commit.

  Args:
    repository: The git repository.
    git_hash: The git hash of the commit.
    path: The path in the repository to the file.

  Returns:
    A string containing the file contents.
  """
  url = '%s/%s/+/%s/%s?format=TEXT' % (_BASE_URL, repository, git_hash, path)
  return base64.b64decode(_Request(url))


def _RequestJson(url):
  """Requests a URL and decodes the JSON result into a dict."""
  return json.loads(_Request(url)[len(_PADDING):])


def _Request(url):
  """Requests a URL with one retry."""
  try:
    response = urlfetch.fetch(url)
    if response.status_code != 200:
      raise urlfetch.Error('Server returned HTTP code %d for %s' %
                           (response.status_code, url))
  except urlfetch.Error:
    # Retry.
    response = urlfetch.fetch(url)
    if response.status_code != 200:
      raise urlfetch.Error('Server returned HTTP code %d for %s' %
                           (response.status_code, url))

  return response.content
