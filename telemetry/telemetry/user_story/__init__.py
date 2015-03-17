# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re
from telemetry.user_story import shared_user_story_state

_next_user_story_id = 0


class UserStory(object):
  """A class styled on unittest.TestCase for creating user story tests.

  Test should override Run to maybe start the application and perform actions
  onto it. To share state between different tests, one can define a
  shared_user_story_state which contains hooks that will be called before &
  after mutiple user stories run and in between runs.

  Args:
    shared_user_story_state_class: subclass of
        telemetry.user_story.shared_user_story_state.SharedUserStoryState.
    name: string name of this user story that can be used for identifying user
        story in results output.
    labels: A list or set of string labels that are used for filtering. See
        user_story.user_story_filter for more information.
    is_local: If true, the user story does not require network.
  """

  def __init__(self, shared_user_story_state_class, name='', labels=None,
               is_local=False, make_javascript_deterministic=True):
    """
    Args:
      make_javascript_deterministic: Whether JavaScript performed on
          the page is made deterministic across multiple runs. This
          requires that the web content is served via Web Page Replay
          to take effect. Does not affect user story containing no web
          contents or where there is the HTTP response mime type is
          not text/html. See also: _InjectScripts method in
          third_party/webpagereplay/httpclient.py.
    """
    assert issubclass(shared_user_story_state_class,
                      shared_user_story_state.SharedUserStoryState)
    self._shared_user_story_state_class = shared_user_story_state_class
    self._name = name
    global _next_user_story_id
    self._id = _next_user_story_id
    _next_user_story_id += 1
    if labels is None:
      labels = set([])
    elif isinstance(labels, list):
      labels = set(labels)
    else:
      assert isinstance(labels, set)
    self._labels = labels
    self._is_local = is_local
    self._make_javascript_deterministic = make_javascript_deterministic

  @property
  def labels(self):
    return self._labels

  @property
  def shared_user_story_state_class(self):
    return self._shared_user_story_state_class

  @property
  def id(self):
    return self._id

  @property
  def name(self):
    return self._name

  def AsDict(self):
    """Converts a user story object to a dict suitable for JSON output."""
    d = {
      'id': self._id,
    }
    if self._name:
      d['name'] = self._name
    return d

  @property
  def file_safe_name(self):
    """A version of display_name that's safe to use as a filename."""
    # Just replace all special characters in the url with underscore.
    return re.sub('[^a-zA-Z0-9]', '_', self.display_name)

  @property
  def display_name(self):
    if self.name:
      return self.name
    else:
      return self.__class__.__name__

  @property
  def is_local(self):
    """Returns True iff this user story does not require network."""
    return self._is_local

  @property
  def serving_dir(self):
    """Returns the absolute path to a directory with hash files to data that
       should be updated from cloud storage, or None if no files need to be
       updated.
    """
    return None

  @property
  def make_javascript_deterministic(self):
    return self._make_javascript_deterministic
