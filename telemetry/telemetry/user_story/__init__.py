# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

_next_user_story_id = 0


class UserStory(object):
  def __init__(self, name=''):
    self._name = name
    global _next_user_story_id
    self._id = _next_user_story_id
    _next_user_story_id += 1

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
