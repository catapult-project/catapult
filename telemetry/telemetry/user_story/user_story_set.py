# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry import user_story as user_story_module


class UserStorySet(object):
  def __init__(self):
    self.user_stories = []

  def AddUserStory(self, user_story):
    assert isinstance(user_story, user_story_module.UserStory)
    self.user_stories.append(user_story)

  @classmethod
  def Name(cls):
    """ Returns the string name of this UserStorySet.
    Note that this should be a classmethod so benchmark_runner script can match
    user story class with its name specified in the run command:
    'Run <User story test name> <User story class name>'
    """
    return cls.__module__.split('.')[-1]

  @classmethod
  def Description(cls):
    """ Return a string explaining in human-understandable terms what this
    user story represents.
    Note that this should be a classmethod so benchmark_runner script can
    display user stories' names along their descriptions in the list commmand.
    """
    if cls.__doc__:
      return cls.__doc__.splitlines()[0]
    else:
      return ''

  def __iter__(self):
    return self.user_stories.__iter__()

  def __len__(self):
    return len(self.user_stories)

  def __getitem__(self, key):
    return self.user_stories[key]

  def __setitem__(self, key, value):
    self.user_stories[key] = value
