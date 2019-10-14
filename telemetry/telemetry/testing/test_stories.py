# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Simple customizable stories and story sets to use in tests."""

import posixpath
import urlparse

from telemetry.core import util
from telemetry import page
from telemetry import story


class TestPage(page.Page):
  def __init__(self, story_set, url, name=None, run_side_effect=None):
    """A simple customizable page.

    Note this uses the SharedPageState, as most stories do, involving
    interactions with a real browser on a real platform.

    Args:
      story_set: An instance of the StorySet object this page belongs to.
      url: A URL for the page to load, in tests usually a local 'file://' URI.
      name: A name for the story. If not given a reasonable default is built
        from the url.
      run_side_effect: Side effect of the story's RunPageInteractions method.
        It should be a callable taking an action_runner.
    """
    if name is None:
      name = _StoryNameFromUrl(url)
    super(TestPage, self).__init__(
        url, story_set, name=name, base_dir=story_set.base_dir)
    self._run_side_effect = run_side_effect

  def RunPageInteractions(self, action_runner):
    if self._run_side_effect is not None:
      self._run_side_effect(action_runner)


def SinglePageStorySet(url=None, name=None, base_dir=None,
                       story_run_side_effect=None):
  """Create a simple StorySet with a single TestPage.

  Args:
    url: An optional URL for the page to load, in tests usually a local
      'file://' URI. Defaults to 'file://blank.html' which, if using the
      default base_dir, points to a simple 'Hello World' html page.
    name: An optional name for the story. If omitted a reasonable default is
      built from the url.
    base_dir: A path on the local file system from which file URIs are served.
      Defaults to serving pages from telemetry/internal/testing.
    story_run_side_effect: Side effect of running the story. See TestPage
      docstring for details.
  """
  if url is None:
    url = 'file://blank.html'
  if base_dir is None:
    base_dir = util.GetUnittestDataDir()
  story_set = story.StorySet(base_dir=base_dir)
  story_set.AddStory(TestPage(story_set, url, name, story_run_side_effect))
  return story_set


def _StoryNameFromUrl(url):
  """Turns e.g. 'file://path/to/name.html' into just 'name'."""
  # Strip off URI scheme, params and query; keep only netloc and path.
  uri = urlparse.urlparse(url)
  filepath = posixpath.basename(uri.netloc + uri.path)
  return posixpath.splitext(posixpath.basename(filepath))[0]
