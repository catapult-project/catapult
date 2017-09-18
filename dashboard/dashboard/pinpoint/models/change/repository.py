# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from dashboard.common import namespaced_stored_object


_REPOSITORIES_KEY = 'repositories'
_URLS_TO_NAMES_KEY = 'repository_urls_to_names'


def RepositoryUrl(name):
  repositories = namespaced_stored_object.Get(_REPOSITORIES_KEY)
  return repositories[name]['repository_url']


def Repository(url, add_if_missing=False):
  if url.endswith('.git'):
    url = url[:-4]

  urls_to_names = namespaced_stored_object.Get(_URLS_TO_NAMES_KEY)
  try:
    return urls_to_names[url]
  except KeyError:
    if add_if_missing:
      return _AddRepository(url)
    raise


def _AddRepository(url):
  name = url.split('/')[-1]

  # Add to main repositories dict.
  repositories = namespaced_stored_object.Get(_REPOSITORIES_KEY)
  if name in repositories:
    raise AssertionError("Attempted to add a repository that's already in the "
                         'Datastore: %s: %s' % (name, url))
  repositories[name] = {'repository_url': url}
  namespaced_stored_object.Set(_REPOSITORIES_KEY, repositories)

  # Add to URL -> name mapping dict.
  urls_to_names = namespaced_stored_object.Get(_URLS_TO_NAMES_KEY)
  urls_to_names[url] = name
  namespaced_stored_object.Set(_URLS_TO_NAMES_KEY, urls_to_names)

  return name
