# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class _Info(object):

  def __init__(self, name, _type=None):
    self._name = name
    self._type = _type

  @property
  def name(self):
    return self._name

  @property
  def type(self):
    return self._type


ANGLE_REVISIONS = _Info('angle revisions', 'GenericSet')
ARCHITECTURES = _Info('architectures', 'GenericSet')
BENCHMARKS = _Info('benchmarks', 'GenericSet')
BENCHMARK_START = _Info('benchmark start', 'DateRange')
BOTS = _Info('bots', 'GenericSet')
BUG_COMPONENTS = _Info('bug components', 'GenericSet')
BUILDS = _Info('builds', 'GenericSet')
CATAPULT_REVISIONS = _Info('catapult revisions', 'GenericSet')
CHROMIUM_COMMIT_POSITIONS = _Info('chromium commit positions', 'GenericSet')
CHROMIUM_REVISIONS = _Info('chromium revisions', 'GenericSet')
GPUS = _Info('gpus', 'GenericSet')
GROUPING_PATH = _Info('grouping path')
LABELS = _Info('labels', 'GenericSet')
LOG_URLS = _Info('log urls', 'GenericSet')
MASTERS = _Info('masters', 'GenericSet')
MEMORY_AMOUNTS = _Info('memory amounts', 'GenericSet')
MERGED_FROM = _Info('merged from', 'RelatedHistogramSet')
MERGED_TO = _Info('merged to', 'RelatedHistogramSet')
OS_NAMES = _Info('os names', 'GenericSet')
OS_VERSIONS = _Info('os versions', 'GenericSet')
OWNERS = _Info('owners', 'GenericSet')
PRODUCT_VERSIONS = _Info('product versions', 'GenericSet')
RELATED_NAMES = _Info('related names', 'GenericSet')
SKIA_REVISIONS = _Info('skia revisions', 'GenericSet')
STORIES = _Info('stories', 'GenericSet')
STORYSET_REPEATS = _Info('storyset repeats', 'GenericSet')
STORY_TAGS = _Info('story tags', 'GenericSet')
TAG_MAP = _Info('tagmap', 'TagMap')
TRACE_START = _Info('trace start', 'DateRange')
TRACE_URLS = _Info('trace urls', 'GenericSet')
V8_COMMIT_POSITIONS = _Info('v8 commit positions', 'DateRange')
V8_REVISIONS = _Info('v8 revisions', 'GenericSet')
WEBRTC_REVISIONS = _Info('webrtc revisions', 'GenericSet')

# DEPRECATED https://github.com/catapult-project/catapult/issues/3507
BUILDBOT = _Info('buildbot')  # BuildbotInfo or MergedBuildbotInfo
INTERACTION_RECORD = _Info('tir', 'GenericSet')
ITERATION = _Info('iteration')  # Legacy name for TELEMETRY
REVISIONS = _Info('revisions')  # RevisionInfo or MergedRevisionInfo
TELEMETRY = _Info('telemetry')  # TelemetryInfo or MergedTelemetryInfo

def GetTypeForName(name):
  for info in globals().itervalues():
    if isinstance(info, _Info) and info.name == name:
      return info.type
