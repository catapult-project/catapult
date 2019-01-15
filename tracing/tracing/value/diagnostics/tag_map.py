# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from tracing.value.diagnostics import diagnostic


class TagMap(diagnostic.Diagnostic):
  __slots__ = '_tags_to_story_names',

  def __init__(self, info):
    super(TagMap, self).__init__()
    self._tags_to_story_names = dict(
        (k, set(v)) for k, v in info.get(
            'tagsToStoryNames', {}).items())

  def __eq__(self, other):
    if not isinstance(other, TagMap):
      return False

    return self.tags_to_story_names == other.tags_to_story_names

  def __hash__(self):
    return id(self)

  def _AsDictInto(self, d):
    d['tagsToStoryNames'] = dict(
        (k, list(v)) for k, v in self.tags_to_story_names.items())

  @staticmethod
  def FromDict(d):
    return TagMap(d)

  @property
  def tags_to_story_names(self):
    return self._tags_to_story_names

  def AddTagAndStoryDisplayName(self, tag, story_display_name):
    if not tag in self.tags_to_story_names:
      self.tags_to_story_names[tag] = set()
    self.tags_to_story_names[tag].add(story_display_name)

  def CanAddDiagnostic(self, other_diagnostic):
    return isinstance(other_diagnostic, TagMap)

  def AddDiagnostic(self, other_diagnostic):
    for name, story_display_names in\
        other_diagnostic.tags_to_story_names.items():
      if not name in self.tags_to_story_names:
        self.tags_to_story_names[name] = set()

      for t in story_display_names:
        self.tags_to_story_names[name].add(t)
