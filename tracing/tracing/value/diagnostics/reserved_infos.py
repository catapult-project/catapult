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


ANGLE_REVISIONS = _Info('angleRevisions', 'GenericSet')
ARCHITECTURES = _Info('architectures', 'GenericSet')
BENCHMARKS = _Info('benchmarks', 'GenericSet')
BENCHMARK_START = _Info('benchmarkStart', 'DateRange')
BOTS = _Info('bots', 'GenericSet')
BUG_COMPONENTS = _Info('bugComponents', 'GenericSet')
BUILDS = _Info('builds', 'GenericSet')
CATAPULT_REVISIONS = _Info('catapultRevisions', 'GenericSet')
CHROMIUM_COMMIT_POSITIONS = _Info('chromiumCommitPositions', 'GenericSet')
CHROMIUM_REVISIONS = _Info('chromiumRevisions', 'GenericSet')
GPUS = _Info('gpus', 'GenericSet')
GROUPING_PATH = _Info('groupingPath')
LABELS = _Info('labels', 'GenericSet')
LOG_URLS = _Info('logUrls', 'GenericSet')
MASTERS = _Info('masters', 'GenericSet')
MEMORY_AMOUNTS = _Info('memoryAmounts', 'GenericSet')
MERGED_FROM = _Info('mergedFrom', 'RelatedHistogramMap')
MERGED_TO = _Info('mergedTo', 'RelatedHistogramMap')
OS_NAMES = _Info('osNames', 'GenericSet')
OS_VERSIONS = _Info('osVersions', 'GenericSet')
OWNERS = _Info('owners', 'GenericSet')
PRODUCT_VERSIONS = _Info('productVersions', 'GenericSet')
RELATED_NAMES = _Info('relatedNames', 'GenericSet')
SKIA_REVISIONS = _Info('skiaRevisions', 'GenericSet')
STORIES = _Info('stories', 'GenericSet')
STORYSET_REPEATS = _Info('storysetRepeats', 'GenericSet')
STORY_TAGS = _Info('storyTags', 'GenericSet')
TAG_MAP = _Info('tagmap', 'TagMap')
TRACE_START = _Info('traceStart', 'DateRange')
TRACE_URLS = _Info('traceUrls', 'GenericSet')
V8_COMMIT_POSITIONS = _Info('v8CommitPositions', 'DateRange')
V8_REVISIONS = _Info('v8Revisions', 'GenericSet')
WEBRTC_REVISIONS = _Info('webrtcRevisions', 'GenericSet')

# DEPRECATED https://github.com/catapult-project/catapult/issues/3507
BUILDBOT = _Info('buildbot')  # BuildbotInfo or MergedBuildbotInfo
INTERACTION_RECORD = _Info('tir', 'GenericSet')
ITERATION = _Info('iteration')  # Legacy name for TELEMETRY
TELEMETRY = _Info('telemetry')  # TelemetryInfo or MergedTelemetryInfo

def GetTypeForName(name):
  for info in globals().itervalues():
    if isinstance(info, _Info) and info.name == name:
      return info.type
