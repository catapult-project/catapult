# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import optparse
import os
import logging
import re

from telemetry.story import typ_expectations


class _StoryMatcher(object):
  def __init__(self, pattern):
    self._regex = None
    if pattern:
      try:
        self._regex = re.compile(pattern)
      except:
        # Provide context since the error that re module provides
        # is not user friendly.
        logging.error('We failed to compile the regex "%s"', pattern)
        raise

  def __nonzero__(self):
    return self._regex is not None

  def HasMatch(self, story):
    return self and bool(self._regex.search(story.name))


class _StoryTagMatcher(object):
  def __init__(self, tags_str):
    self._tags = tags_str.split(',') if tags_str else None

  def __nonzero__(self):
    return self._tags is not None

  def HasLabelIn(self, story):
    return self and bool(story.tags.intersection(self._tags))


class StoryFilterFactory(object):
  """This factory reads static global configuration for a StoryFilter.

  Static global configuration includes commandline flags and ProjectConfig.

  It then provides a way to create a StoryFilter by only providing
  the runtime configuration.
  """

  @classmethod
  def BuildStoryFilter(cls, benchmark_name, platform_tags,
                       abridged_story_set_tag):
    expectations = typ_expectations.StoryExpectations(benchmark_name)
    expectations.SetTags(platform_tags or [])
    if cls._expectations_file and os.path.exists(cls._expectations_file):
      with open(cls._expectations_file) as fh:
        expectations.GetBenchmarkExpectationsFromParser(fh.read())
    if cls._run_full_story_set:
      abridged_story_set_tag = None
    return StoryFilter(
        expectations, abridged_story_set_tag, cls._story_filter,
        cls._story_filter_exclude,
        cls._story_tag_filter, cls._story_tag_filter_exclude,
        cls._shard_begin_index, cls._shard_end_index, cls._run_disabled_stories)

  @classmethod
  def AddCommandLineArgs(cls, parser):
    group = optparse.OptionGroup(parser, 'User story filtering options')
    group.add_option(
        '--story-filter',
        help='Use only stories whose names match the given filter regexp.')
    group.add_option(
        '--story-filter-exclude',
        help='Exclude stories whose names match the given filter regexp.')
    group.add_option(
        '--story-tag-filter',
        help='Use only stories that have any of these tags')
    group.add_option(
        '--story-tag-filter-exclude',
        help='Exclude stories that have any of these tags')
    common_story_shard_help = (
        'Indices start at 0, and have the same rules as python slices,'
        ' e.g.  [4, 5, 6, 7, 8][0:3] -> [4, 5, 6])')
    group.add_option(
        '--story-shard-begin-index', type='int', dest='story_shard_begin_index',
        help=('Beginning index of set of stories to run. If this is ommited, '
              'the starting index will be from the first story in the benchmark'
              + common_story_shard_help))
    group.add_option(
        '--story-shard-end-index', type='int', dest='story_shard_end_index',
        help=('End index of set of stories to run. Value will be '
              'rounded down to the number of stories. Negative values not'
              'allowed. If this is ommited, the end index is the final story'
              'of the benchmark. '+ common_story_shard_help))
    # This should be renamed to --also-run-disabled-stories.
    group.add_option('-d', '--also-run-disabled-tests',
                     dest='run_disabled_stories',
                     action='store_true', default=False,
                     help='Ignore expectations.config disabling.')
    group.add_option(
        '--run-full-story-set', action='store_true', default=False,
        help='Whether to run the complete set of stories instead '
        'of an abridged version. Note that if the story set '
        'does not provide the information required to abridge it, '
        'then this argument will have no impact.')
    parser.add_option_group(group)

  @classmethod
  def ProcessCommandLineArgs(cls, parser, args, environment=None):
    del parser
    cls._story_filter = args.story_filter
    cls._story_filter_exclude = args.story_filter_exclude
    cls._story_tag_filter = args.story_tag_filter
    cls._story_tag_filter_exclude = args.story_tag_filter_exclude
    cls._shard_begin_index = args.story_shard_begin_index or 0
    cls._shard_end_index = args.story_shard_end_index
    if environment and environment.expectations_files:
      assert len(environment.expectations_files) == 1
      cls._expectations_file = environment.expectations_files[0]
    else:
      cls._expectations_file = None
    cls._run_disabled_stories = args.run_disabled_stories
    cls._run_full_story_set = args.run_full_story_set


class StoryFilter(object):
  """Logic to decide whether to run, skip, or ignore stories."""

  def __init__(
      self, expectations=None, abridged_story_set_tag=None, story_filter=None,
      story_filter_exclude=None,
      story_tag_filter=None, story_tag_filter_exclude=None,
      shard_begin_index=0, shard_end_index=None, run_disabled_stories=False):
    self._expectations = expectations
    self._include_regex = _StoryMatcher(story_filter)
    self._exclude_regex = _StoryMatcher(story_filter_exclude)
    self._include_tags = _StoryTagMatcher(story_tag_filter)
    self._exclude_tags = _StoryTagMatcher(story_tag_filter_exclude)
    self._shard_begin_index = shard_begin_index
    self._shard_end_index = shard_end_index
    if self._shard_end_index is not None:
      if self._shard_end_index < 0:
        raise ValueError(
            'shard end index cannot be less than 0, since stories are indexed '
            'with positive numbers')
      if (self._shard_begin_index is not None and
          self._shard_end_index <= self._shard_begin_index):
        raise ValueError(
            'shard end index cannot be less than or equal to shard begin index')
    self._run_disabled_stories = run_disabled_stories
    self._abridged_story_set_tag = abridged_story_set_tag

  def FilterStories(self, stories):
    """Filters the given stories, using filters provided in the command line.

    This filter causes stories to become completely ignored, and therefore
    they will not show up in test results output.

    Story sharding is done before exclusion and inclusion is done.

    Args:
      stories: A list of stories.

    Returns:
      A list of remaining stories.
    """
    # TODO(crbug.com/982027): Support for --story=<exact story name>
    # should be implemented here.
    if self._shard_begin_index < 0:
      self._shard_begin_index = 0
    if self._shard_end_index is None:
      self._shard_end_index = len(stories)

    stories = stories[self._shard_begin_index:self._shard_end_index]

    final_stories = []
    for story in stories:
      # Exclude filters take priority.
      if self._exclude_tags.HasLabelIn(story):
        continue
      if self._exclude_regex.HasMatch(story):
        continue

      if self._include_tags and not self._include_tags.HasLabelIn(story):
        continue
      if self._include_regex and not self._include_regex.HasMatch(story):
        continue
      if (self._abridged_story_set_tag and
          self._abridged_story_set_tag not in story.tags):
        continue

      final_stories.append(story)

    return final_stories

  def ShouldSkip(self, story):
    """Decides whether a story should be marked skipped.

    The difference between marking a story skipped and simply not running
    it is important for tracking purposes. Officially skipped stories show
    up in test results outputs.

    Args:
      story: A story.Story object.

    Returns:
      A skip reason string if the story should be skipped, otherwise an
      empty string.
    """
    # TODO(crbug.com/982027): Support for --story=<exact story name>
    # should be implemented here.
    disabled = self._expectations.IsStoryDisabled(story)
    if disabled and self._run_disabled_stories:
      logging.warning(
          'Force running a disabled story %s even though it was disabled with '
          'the following reason: %s' % (story.name, disabled))
      return ''
    return disabled
