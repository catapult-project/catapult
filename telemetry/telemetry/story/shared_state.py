# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class SharedState(object):
  """A class that manages the test state across multiple stories.
  It's styled on unittest.TestCase for handling test setup & teardown logic.

  """

  def __init__(self, test, options, story_set):
    """ This method is styled on unittest.TestCase.setUpClass.
    Override to do any action before running stories that
    share this same state.
    Args:
      test: a page_test.PageTest instance.
      options: a BrowserFinderOptions instance that contains command line
        options.
      story_set: a story.StorySet instance.
    """
    pass

  @property
  def platform(self):
    """ Override to return the platform which stories that share this same
    state will be run on.
    """
    raise NotImplementedError()

  def WillRunStory(self, story):
    """ Override to do any action before running each one of all stories
    that share this same state.
    This method is styled on unittest.TestCase.setUp.
    """
    raise NotImplementedError()

  def DidRunStory(self, results):
    """ Override to do any action after running each of all stories that
    share this same state.
    This method is styled on unittest.TestCase.tearDown.
    """
    raise NotImplementedError()

  def GetTestExpectationAndSkipValue(self, expectations):
    """ Return test expectation and skip value instance in case expectation
    is 'skip'. This is run after WillRunStory and before RunStory.
    """
    raise NotImplementedError()

  def RunStory(self, results):
    """ Override to do any action before running each one of all stories
    that share this same state.
    This method is styled on unittest.TestCase.run.
    """
    raise NotImplementedError()

  def TearDownState(self):
    """ Override to do any action after running multiple stories that
    share this same state.
    This method is styled on unittest.TestCase.tearDownClass.
    """
    raise NotImplementedError()
