# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class SharedUserStoryState(object):
  """A class that manages the test state across multiple user stories.
  It's styled on unittest.TestCase for handling test setup & teardown logic.

  """

  def __init__(self, test, options, user_story_set):
    """ This method is styled on unittest.TestCase.setUpClass.
    Override to do any action before running user stories that
    share this same state.
    Args:
      test: a page_test.PageTest instance.
      options: a BrowserFinderOptions instance that contains command line
        options.
      user_story_set: a user_story_set.UserStorySet instance.
    """
    pass

  @property
  def platform(self):
    """ Override to return the platform which user stories that share this same
    state will be run on.
    """
    raise NotImplementedError()

  def WillRunUserStory(self, user_story):
    """ Override to do any action before running each one of all user stories
    that share this same state.
    This method is styled on unittest.TestCase.setUp.
    """
    raise NotImplementedError()

  def DidRunUserStory(self, results):
    """ Override to do any action after running each of all user stories that
    share this same state.
    This method is styled on unittest.TestCase.tearDown.
    """
    raise NotImplementedError()

  def GetTestExpectationAndSkipValue(self, expectations):
    """ Return test expectation and skip value instance in case expectation
    is 'skip'. This is run after WillRunUserStory and before RunUserStory.
    """
    raise NotImplementedError()

  def RunUserStory(self, results):
    """ Override to do any action before running each one of all user stories
    that share this same state.
    This method is styled on unittest.TestCase.run.
    """
    raise NotImplementedError()

  def TearDownState(self, results):
    """ Override to do any action after running multiple user stories that
    share this same state.
    This method is styled on unittest.TestCase.tearDownClass.
    """
    raise NotImplementedError()
