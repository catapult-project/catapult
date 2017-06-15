# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import math
import random
import uuid


# pylint: disable=too-many-lines
# TODO(benjhayden): Split this file up.


# This should be equal to sys.float_info.max, but that value might differ
# between platforms, whereas ECMA Script specifies this value for all platforms.
# The specific value should not matter in normal practice.
JS_MAX_VALUE = 1.7976931348623157e+308


MERGED_FROM_DIAGNOSTIC_KEY = 'merged from'


# Converts the given percent to a string in the following format:
# 0.x produces '0x0',
# 0.xx produces '0xx',
# 0.xxy produces '0xx_y',
# 1.0 produces '100'.
def PercentToString(percent):
  if percent < 0 or percent > 1:
    raise ValueError('percent must be in [0,1]')
  if percent == 0:
    return '000'
  if percent == 1:
    return '100'
  s = str(percent)
  if s[1] != '.':
    raise ValueError('Unexpected percent')
  s += '0' * max(4 - len(s), 0)
  if len(s) > 4:
    s = s[:4] + '_' + s[4:]
  return '0' + s[2:]


# This variation of binary search returns the index |hi| into |ary| for which
# callback(ary[hi]) < 0 and callback(ary[hi-1]) >= 0
# This function assumes that map(callback, ary) is sorted descending.
def FindHighIndexInSortedArray(ary, callback):
  lo = 0
  hi = len(ary)
  while lo < hi:
    mid = (lo + hi) >> 1
    if callback(ary[mid]) >= 0:
      lo = mid + 1
    else:
      hi = mid
  return hi


# Modifies |samples| in-place to reduce its length to |count|, discarding random
# elements.
def UniformlySampleArray(samples, count):
  while len(samples) > count:
    samples.pop(int(random.uniform(0, len(samples))))
  return samples


# When processing a stream of samples, call this method for each new sample in
# order to decide whether to keep it in |samples|.
# Modifies |samples| in-place such that its length never exceeds |num_samples|.
# After |stream_length| samples have been processed, each sample has equal
# probability of being retained in |samples|.
# The order of samples is not preserved after |stream_length| exceeds
# |num_samples|.
def UniformlySampleStream(samples, stream_length, new_element, num_samples):
  if stream_length <= num_samples:
    if len(samples) >= stream_length:
      samples[stream_length - 1] = new_element
    else:
      samples.append(new_element)
    return

  prob_keep = num_samples / stream_length
  if random.random() > prob_keep:
    # reject new_sample
    return

  # replace a random element
  samples[math.floor(random.random() * num_samples)] = new_element


# Merge two sets of samples that were assembled using UniformlySampleStream().
# Modify |a_samples| in-place such that all of the samples in |a_samples| and
# |b_samples| have equal probability of being retained in |a_samples|.
def MergeSampledStreams(a_samples, a_stream_length,
                        b_samples, b_stream_length, num_samples):
  if b_stream_length < num_samples:
    for i in xrange(min(b_stream_length, len(b_samples))):
      UniformlySampleStream(
          a_samples, a_stream_length + i + 1, b_samples[i], num_samples)
    return

  if a_stream_length < num_samples:
    temp_samples = list(b_samples)
    for i in xrange(min(a_stream_length, len(a_samples))):
      UniformlySampleStream(
          temp_samples, b_stream_length + i + 1, a_samples[i], num_samples)
    for i in xrange(len(temp_samples)):
      a_samples[i] = temp_samples[i]
    return

  prob_swap = b_stream_length / (a_stream_length + b_stream_length)
  for i in xrange(min(num_samples, len(b_samples))):
    if random.random() < prob_swap:
      a_samples[i] = b_samples[i]


def Percentile(ary, percent):
  if percent < 0 or percent > 1:
    raise ValueError('percent must be in [0,1]')
  ary = list(ary)
  ary.sort()
  return ary[int((len(ary) - 1) * percent)]


class Range(object):
  def __init__(self):
    self._empty = True
    self._min = None
    self._max = None

  @staticmethod
  def FromExplicitRange(lower, upper):
    r = Range()
    r._min = lower
    r._max = upper
    r._empty = False
    return r

  @property
  def empty(self):
    return self._empty

  @property
  def min(self):
    return self._min

  @property
  def max(self):
    return self._max

  @property
  def center(self):
    return (self._min + self._max) * 0.5

  @property
  def duration(self):
    if self.empty:
      return 0
    return self._max - self._min

  def AddValue(self, x):
    if self._empty:
      self._empty = False
      self._min = x
      self._max = x
      return

    self._max = max(x, self._max)
    self._min = min(x, self._min)

  def AddRange(self, other):
    if other.empty:
      return
    self.AddValue(other.min)
    self.AddValue(other.max)


# This class computes statistics online in O(1).
class RunningStatistics(object):
  def __init__(self):
    self._count = 0
    self._mean = 0.0
    self._max = -JS_MAX_VALUE
    self._min = JS_MAX_VALUE
    self._sum = 0.0
    self._variance = 0.0
    # Mean of logarithms of samples, or None if any samples were <= 0.
    self._meanlogs = 0.0

  @property
  def count(self):
    return self._count

  @property
  def geometric_mean(self):
    if self._meanlogs is None:
      return None
    return math.exp(self._meanlogs)

  @property
  def mean(self):
    if self._count == 0:
      return None
    return self._mean

  @property
  def max(self):
    return self._max

  @property
  def min(self):
    return self._min

  @property
  def sum(self):
    return self._sum

  @property
  def variance(self):
    if self.count == 0:
      return None
    if self.count == 1:
      return 0
    return self._variance / (self.count - 1)

  @property
  def stddev(self):
    if self.count == 0:
      return None
    return math.sqrt(self.variance)

  def Add(self, x):
    self._count += 1
    x = float(x)
    self._max = max(self._max, x)
    self._min = min(self._min, x)
    self._sum += x

    if x <= 0.0:
      self._meanlogs = None
    elif self._meanlogs is not None:
      self._meanlogs += (math.log(abs(x)) - self._meanlogs) / self.count

    # The following uses Welford's algorithm for computing running mean and
    # variance. See http://www.johndcook.com/blog/standard_deviation.
    if self.count == 1:
      self._mean = x
      self._variance = 0.0
    else:
      old_mean = self._mean
      old_variance = self._variance

      # Using the 2nd formula for updating the mean yields better precision but
      # it doesn't work for the case oldMean is Infinity. Hence we handle that
      # case separately.
      if abs(old_mean) == float('inf'):
        self._mean = self._sum / self.count
      else:
        self._mean = old_mean + float(x - old_mean) / self.count
      self._variance = old_variance + (x - old_mean) * (x - self._mean)

  def Merge(self, other):
    result = RunningStatistics()
    result._count = self._count + other._count
    result._sum = self._sum + other._sum
    result._min = min(self._min, other._min)
    result._max = max(self._max, other._max)
    if result._count == 0:
      result._mean = 0.0
      result._variance = 0.0
      result._meanlogs = 0.0
    else:
      # Combine the mean and the variance using the formulas from
      # https://goo.gl/ddcAep.
      result._mean = float(result._sum) / result._count
      delta_mean = (self._mean or 0.0) - (other._mean or 0.0)
      result._variance = self._variance + other._variance + (
          self._count * other._count * delta_mean * delta_mean / result._count)

      # Merge the arithmetic means of logarithms of absolute values of samples,
      # weighted by counts.
      if self._meanlogs is None or other._meanlogs is None:
        result._meanlogs = None
      else:
        result._meanlogs = (self._count * self._meanlogs +
                            other._count * other._meanlogs) / result._count
    return result

  def AsDict(self):
    if self._count == 0:
      return []

    # Javascript automatically converts between ints and floats.
    # It's more efficient to serialize integers as ints than floats.
    def FloatAsFloatOrInt(x):
      if x is not None and x.is_integer():
        return int(x)
      return x

    # It's more efficient to serialize these fields in an array. If you add any
    # other fields, you should re-evaluate whether it would be more efficient to
    # serialize as a dict.
    return [
        self._count,
        FloatAsFloatOrInt(self._max),
        FloatAsFloatOrInt(self._meanlogs),
        FloatAsFloatOrInt(self._mean),
        FloatAsFloatOrInt(self._min),
        FloatAsFloatOrInt(self._sum),
        FloatAsFloatOrInt(self._variance),
    ]

  @staticmethod
  def FromDict(dct):
    result = RunningStatistics()
    if len(dct) != 7:
      return result

    def AsFloatOrNone(x):
      if x is None:
        return x
      return float(x)
    [result._count, result._max, result._meanlogs, result._mean, result._min,
     result._sum, result._variance] = [int(dct[0])] + [
         AsFloatOrNone(x) for x in dct[1:]]
    return result


class Diagnostic(object):
  def __init__(self):
    self._guid = None

  @property
  def guid(self):
    if self._guid is None:
      self._guid = str(uuid.uuid4())
    return self._guid

  @guid.setter
  def guid(self, g):
    assert self._guid is None
    self._guid = g

  @property
  def has_guid(self):
    return self._guid is not None

  def AsDictOrReference(self):
    if self._guid:
      return self._guid
    return self.AsDict()

  def AsDict(self):
    dct = {'type': self.__class__.__name__}
    if self._guid:
      dct['guid'] = self._guid
    self._AsDictInto(dct)
    return dct

  def _AsDictInto(self, unused_dct):
    raise NotImplementedError

  @staticmethod
  def FromDict(dct):
    if dct['type'] not in Diagnostic.REGISTRY:
      raise ValueError('Unrecognized diagnostic type: ' + dct['type'])
    diagnostic = Diagnostic.REGISTRY[dct['type']].FromDict(dct)
    if 'guid' in dct:
      diagnostic.guid = dct['guid']
    return diagnostic

  def Inline(self):
    """Inlines a shared diagnostic.

    Any diagnostic that has a guid will be serialized as a reference, because it
    is assumed that diagnostics with guids are shared. This method removes the
    guid so that the diagnostic will be serialized by value.

    Inling is used for example in the dashboard, where certain types of shared
    diagnostics that vary on a per-upload basis are inlined for efficiency
    reasons.
    """
    self._guid = None

  def CanAddDiagnostic(self, unused_other_diagnostic, unused_name,
                       unused_parent_hist, unused_other_parent_hist):
    return False

  def AddDiagnostic(self, unused_other_diagnostic, unused_name,
                    unused_parent_hist, unused_other_parent_hist):
    raise Exception('Abstract virtual method: subclasses must override '
                    'this method if they override canAddDiagnostic')


Diagnostic.REGISTRY = {}

def RegisterDiagnosticTypes(baseclass=Diagnostic):
  for subclass in baseclass.__subclasses__():  # pylint: disable=no-member
    Diagnostic.REGISTRY[subclass.__name__] = subclass
    RegisterDiagnosticTypes(subclass)


class Ownership(Diagnostic):

  NAME = 'owners'

  def __init__(self, emails, component=None):
    super(Ownership, self).__init__()

    emails = emails or []

    self._emails = emails[:]

    if (component is None) or isinstance(component, basestring):
      self._component = component
    else:
      raise TypeError('component must be None or string')

  @property
  def emails(self):
    return self._emails[:]

  @property
  def component(self):
    return self._component

  def _AsDictInto(self, dct):
    dct['emails'] = self.emails

    if self.component is not None:
      dct['component'] = self.component

  @staticmethod
  def FromDict(dct):
    return Ownership(dct.get('emails'), dct.get('component'))

class Breakdown(Diagnostic):
  def __init__(self):
    super(Breakdown, self).__init__()
    self._values = {}
    self._color_scheme = None

  @property
  def color_scheme(self):
    return self._color_scheme

  @staticmethod
  def FromDict(d):
    result = Breakdown()
    result._color_scheme = d.get('colorScheme')
    for name, value in d['values'].iteritems():
      if value in ['NaN', 'Infinity', '-Infinity']:
        value = float(value)
      result.Set(name, value)
    return result

  def _AsDictInto(self, d):
    d['values'] = {}
    for name, value in self:
      # JSON serializes NaN and the infinities as 'null', preventing
      # distinguishing between them. Override that behavior by serializing them
      # as their Javascript string names, not their python string names since
      # the reference implementation is in Javascript.
      if math.isnan(value):
        value = 'NaN'
      elif math.isinf(value):
        if value > 0:
          value = 'Infinity'
        else:
          value = '-Infinity'
      d['values'][name] = value
    if self._color_scheme:
      d['colorScheme'] = self._color_scheme

  def Set(self, name, value):
    assert isinstance(name, basestring)
    assert isinstance(value, (int, float))
    self._values[name] = value

  def Get(self, name):
    return self._values.get(name, 0)

  def __iter__(self):
    for name, value in self._values.iteritems():
      yield name, value


# A Generic diagnostic can contain any Plain-Ol'-Data objects that can be
# serialized using JSON.stringify(): null, boolean, number, string, array, dict.
class Generic(Diagnostic):
  def __init__(self, value):
    super(Generic, self).__init__()
    self._value = value

  @property
  def value(self):
    return self._value

  def _AsDictInto(self, dct):
    dct['value'] = self.value

  @staticmethod
  def FromDict(dct):
    return Generic(dct['value'])


class DateRange(Diagnostic):
  def __init__(self, ms):
    super(DateRange, self).__init__()
    self._range = Range()
    self._range.AddValue(ms)

  @property
  def min_date(self):
    return datetime.datetime.fromtimestamp(self._range.min / 1000)

  @property
  def max_date(self):
    return datetime.datetime.fromtimestamp(self._range.max / 1000)

  @property
  def duration_ms(self):
    return self._range.duration

  def _AsDictInto(self, dct):
    dct['min'] = self._range.min
    if self.duration_ms == 0:
      return
    dct['max'] = self._range.max

  @staticmethod
  def FromDict(dct):
    dr = DateRange(dct['min'])
    if 'max' in dct:
      dr._range.AddValue(dct['max'])
    return dr

  def CanAddDiagnostic(self, other_diagnostic, unused_name=None,
                       unused_parent_hist=None, unused_other_parent_hist=None):
    return isinstance(other_diagnostic, DateRange)

  def AddDiagnostic(self, other_diagnostic, unused_name=None,
                    unused_parent_hist=None, unused_other_parent_hist=None):
    self._range.AddRange(other_diagnostic._range)

class HistogramRef(object):
  def __init__(self, guid):
    self._guid = guid

  @property
  def guid(self):
    return self._guid


class RelatedHistogramSet(Diagnostic):
  def __init__(self, histograms=()):
    super(RelatedHistogramSet, self).__init__()
    self._histograms_by_guid = {}
    for hist in histograms:
      self.Add(hist)

  def Add(self, hist):
    assert isinstance(hist, (Histogram, HistogramRef))
    assert not self.Has(hist)
    self._histograms_by_guid[hist.guid] = hist

  def Has(self, hist):
    return hist.guid in self._histograms_by_guid

  def __len__(self):
    return len(self._histograms_by_guid)

  def __iter__(self):
    for hist in self._histograms_by_guid.itervalues():
      yield hist

  def Resolve(self, histograms, required=False):
    for hist in self:
      if isinstance(hist, Histogram):
        continue
      guid = hist.guid
      hist = histograms.LookupHistogram(guid)
      if isinstance(hist, Histogram):
        self._histograms_by_guid[guid] = hist
      else:
        assert not required, guid

  def _AsDictInto(self, d):
    d['guids'] = []
    for hist in self:
      d['guids'].append(hist.guid)

  @staticmethod
  def FromDict(d):
    return RelatedHistogramSet(HistogramRef(guid) for guid in d['guids'])


class RelatedHistogramMap(Diagnostic):
  def __init__(self):
    super(RelatedHistogramMap, self).__init__()
    self._histograms_by_name = {}

  def Get(self, name):
    return self._histograms_by_name.get(name)

  def Set(self, name, hist):
    assert isinstance(hist, (Histogram, HistogramRef))
    self._histograms_by_name[name] = hist

  def Add(self, hist):
    self.Set(hist.name, hist)

  def __len__(self):
    return len(self._histograms_by_name)

  def __iter__(self):
    for name, hist in self._histograms_by_name.iteritems():
      yield name, hist

  def Resolve(self, histograms, required=False):
    for name, hist in self:
      if not isinstance(hist, HistogramRef):
        continue

      guid = hist.guid
      hist = histograms.LookupHistogram(guid)
      if isinstance(hist, Histogram):
        self._histograms_by_name[name] = hist
      else:
        assert not required, guid

  def _AsDictInto(self, d):
    d['values'] = {}
    for name, hist in self:
      d['values'][name] = hist.guid

  @staticmethod
  def FromDict(d):
    result = RelatedHistogramMap()
    for name, guid in d['values'].iteritems():
      result.Set(name, HistogramRef(guid))
    return result


class RelatedHistogramBreakdown(RelatedHistogramMap):
  def __init__(self):
    super(RelatedHistogramBreakdown, self).__init__()
    self._color_scheme = None

  def Set(self, name, hist):
    if not isinstance(hist, HistogramRef):
      assert isinstance(hist, Histogram)
      # All Histograms must have the same unit.
      for _, other_hist in self:
        expected_unit = other_hist.unit
        assert expected_unit == hist.unit, (
            'Units mismatch ' + expected_unit + ' != ' + hist.unit)
        break  # Only the first Histogram needs to be checked.
    super(RelatedHistogramBreakdown, self).Set(name, hist)

  def _AsDictInto(self, d):
    RelatedHistogramMap._AsDictInto(self, d)
    if self._color_scheme:
      d['colorScheme'] = self._color_scheme

  @staticmethod
  def FromDict(d):
    result = RelatedHistogramBreakdown()
    for name, guid in d['values'].iteritems():
      result.Set(name, HistogramRef(guid))
    if 'colorScheme' in d:
      result._color_scheme = d['colorScheme']
    return result


class TagMap(Diagnostic):
  NAME = 'tagmap'

  def __init__(self, info):
    super(TagMap, self).__init__()
    self._tags_to_story_names = dict(
        (k, set(v)) for k, v in info.get(
            'tagsToStoryNames', {}).iteritems())

  def _AsDictInto(self, d):
    d['tagsToStoryNames'] = dict(
        (k, list(v)) for k, v in self.tags_to_story_names.iteritems())

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

  def CanAddDiagnostic(self, other_diagnostic, unused_name,
                       unused_parent_hist, unused_other_parent_hist):
    return isinstance(other_diagnostic, TagMap)

  def AddDiagnostic(self, other_diagnostic, unused_name,
                    unused_parent_hist, unused_other_parent_hist):
    for name, story_display_names in\
        other_diagnostic.tags_to_story_names.iteritems():
      if not name in self.tags_to_story_names:
        self.tags_to_story_names[name] = set()

      for t in story_display_names:
        self.tags_to_story_names[name].add(t)


class BuildbotInfo(Diagnostic):
  NAME = 'buildbot'

  def __init__(self, info):
    super(BuildbotInfo, self).__init__()
    self._display_master_name = info.get('displayMasterName', '')
    self._display_bot_name = info.get('displayBotName', '')
    self._buildbot_master_name = info.get('buildbotMasterName', '')
    self._buildbot_name = info.get('buildbotName', '')
    self._build_number = info.get('buildNumber', 0)
    self._log_uri = info.get('logUri', '')

  def __eq__(self, other):
    if self.display_master_name != other.display_master_name:
      return False
    if self.display_bot_name != other.display_bot_name:
      return False
    if self.buildbot_master_name != other.buildbot_master_name:
      return False
    if self.buildbot_name != other.buildbot_name:
      return False
    if self.build_number != other.build_number:
      return False
    if self.log_uri != other.log_uri:
      return False
    return True

  def __ne__(self, other):
    return not self == other

  def _AsDictInto(self, d):
    d['displayMasterName'] = self.display_master_name
    d['displayBotName'] = self.display_bot_name
    d['buildbotMasterName'] = self.buildbot_master_name
    d['buildbotName'] = self.buildbot_name
    d['buildNumber'] = self.build_number
    d['logUri'] = self.log_uri

  @staticmethod
  def FromDict(d):
    return BuildbotInfo(d)

  @property
  def display_master_name(self):
    return self._display_master_name

  @property
  def display_bot_name(self):
    return self._display_bot_name

  @property
  def buildbot_master_name(self):
    return self._buildbot_master_name

  @property
  def buildbot_name(self):
    return self._buildbot_name

  @property
  def build_number(self):
    return self._build_number

  @property
  def log_uri(self):
    return self._log_uri


class RevisionInfo(Diagnostic):

  NAME = 'revisions'

  def __init__(self, info):
    super(RevisionInfo, self).__init__()
    self._chromium_commit_position = info.get('chromiumCommitPosition', None)
    self._v8_commit_position = info.get('v8CommitPosition', None)
    self._chromium = info.get('chromium', [])
    self._v8 = info.get('v8', [])
    self._catapult = info.get('catapult', [])
    self._angle = info.get('angle', [])
    self._skia = info.get('skia', [])
    self._webrtc = info.get('webrtc', [])

  @property
  def chromium_commit_position(self):
    return self._chromium_commit_position

  @property
  def v8_commit_position(self):
    return self._v8_commit_position

  @property
  def v8(self):
    return self._v8

  @property
  def catapult(self):
    return self._catapult

  @property
  def angle(self):
    return self._angle

  @property
  def skia(self):
    return self._skia

  @property
  def webrtc(self):
    return self._webrtc

  @property
  def chromium(self):
    return self._chromium

  def _AsDictInto(self, d):
    d['chromiumCommitPosition'] = self._chromium_commit_position
    d['v8CommitPosition'] = self._v8_commit_position
    d['chromium'] = self._chromium
    d['v8'] = self.v8
    d['catapult'] = self.catapult
    d['angle'] = self.angle
    d['skia'] = self.skia
    d['webrtc'] = self.webrtc

  @staticmethod
  def FromDict(d):
    return RevisionInfo(d)


# TODO(benjhayden): Unify this with telemetry's IterationInfo.
class TelemetryInfo(Diagnostic):
  NAME = 'telemetry'

  def __init__(self):
    super(TelemetryInfo, self).__init__()
    self._benchmark_name = ''
    self._benchmark_start = None
    self._label = ''
    self._legacy_tir_label = ''
    self._story_display_name = ''
    self._story_grouping_keys = {}
    self._story_url = ''
    self._storyset_repeat_counter = None

  def __eq__(self, other):
    if self.benchmark_name != other.benchmark_name:
      return False
    if self.benchmark_start != other.benchmark_start:
      return False
    if self.label != other.label:
      return False
    if self.legacy_tir_label != other.legacy_tir_label:
      return False
    if self.story_display_name != other.story_display_name:
      return False
    if self.story_grouping_keys != other.story_grouping_keys:
      return False
    if self.story_url != other.story_url:
      return False
    if self.storyset_repeat_counter != other.storyset_repeat_counter:
      return False
    return True

  def __ne__(self, other):
    return not self == other

  def AddInfo(self, info):
    if 'benchmarkName' in info:
      self._benchmark_name = info['benchmarkName']
    if 'benchmarkStartMs' in info:
      self._benchmark_start = info['benchmarkStartMs']
    if 'label' in info:
      self._label = info['label']
    if 'storyDisplayName' in info:
      self._story_display_name = info['storyDisplayName']
    if 'storyGroupingKeys' in info:
      self._story_grouping_keys = info['storyGroupingKeys']
    if 'storysetRepeatCounter' in info:
      self._storyset_repeat_counter = info['storysetRepeatCounter']
    if 'legacyTIRLabel' in info:
      self._legacy_tir_label = info['legacyTIRLabel']

  def _AsDictInto(self, d):
    d['benchmarkName'] = self.benchmark_name
    d['benchmarkStartMs'] = self.benchmark_start
    d['label'] = self.label
    d['storyDisplayName'] = self.story_display_name
    d['storyGroupingKeys'] = self.story_grouping_keys
    d['storysetRepeatCounter'] = self.storyset_repeat_counter
    d['legacyTIRLabel'] = self.legacy_tir_label

  @property
  def benchmark_name(self):
    return self._benchmark_name

  @property
  def benchmark_start(self):
    return self._benchmark_start

  @property
  def label(self):
    return self._label

  @property
  def story_display_name(self):
    return self._story_display_name

  @property
  def story_grouping_keys(self):
    return self._story_grouping_keys

  @property
  def storyset_repeat_counter(self):
    return self._storyset_repeat_counter

  @property
  def story_url(self):
    return self._story_url

  @property
  def legacy_tir_label(self):
    return self._legacy_tir_label

  @staticmethod
  def FromDict(d):
    info = TelemetryInfo()
    info.AddInfo(d)
    return info


class DeviceInfo(Diagnostic):
  NAME = 'device'

  def __init__(self):
    super(DeviceInfo, self).__init__()
    self._chrome_version = ''
    self._os_name = ''
    self._os_version = ''
    self._gpu_info = None
    self._arch = None
    self._ram = 0

  def __eq__(self, other):
    if self.chrome_version != other.chrome_version:
      return False
    if self.os_name != other.os_name:
      return False
    if self.os_version != other.os_version:
      return False
    if self.gpu_info != other.gpu_info:
      return False
    if self.arch != other.arch:
      return False
    if self.ram != other.ram:
      return False
    return True

  def __ne__(self, other):
    return not self == other

  @staticmethod
  def FromDict(d):
    info = DeviceInfo()
    info.chrome_version = d.get('chromeVersion', '')
    info.os_name = d.get('osName', '')
    info.os_version = d.get('osVersion', '')
    info.gpu_info = d.get('gpuInfo')
    info.arch = d.get('arch')
    info.ram = d.get('ram', 0)
    return info

  def _AsDictInto(self, d):
    d['chromeVersion'] = self.chrome_version
    d['osName'] = self.os_name
    d['osVersion'] = self.os_version
    d['gpuInfo'] = self.gpu_info
    d['arch'] = self.arch
    d['ram'] = self.ram

  @property
  def chrome_version(self):
    return self._chrome_version

  @chrome_version.setter
  def chrome_version(self, v):
    self._chrome_version = v

  @property
  def os_name(self):
    return self._os_name

  @os_name.setter
  def os_name(self, v):
    self._os_name = v

  @property
  def os_version(self):
    return self._os_version

  @os_version.setter
  def os_version(self, v):
    self._os_version = v

  @property
  def gpu_info(self):
    return self._gpu_info

  @gpu_info.setter
  def gpu_info(self, v):
    self._gpu_info = v

  @property
  def arch(self):
    return self._arch

  @arch.setter
  def arch(self, v):
    self._arch = v

  @property
  def ram(self):
    return self._ram

  @ram.setter
  def ram(self, v):
    self._ram = v


class RelatedEventSet(Diagnostic):
  def __init__(self):
    super(RelatedEventSet, self).__init__()
    self._events_by_stable_id = {}

  def Add(self, event):
    self._events_by_stable_id[event['stableId']] = event

  def __len__(self):
    return len(self._events_by_stable_id)

  def __iter__(self):
    for event in self._events_by_stable_id.itervalues():
      yield event

  @staticmethod
  def FromDict(d):
    result = RelatedEventSet()
    for event in d['events']:
      result.Add(event)
    return result

  def _AsDictInto(self, d):
    d['events'] = [event for event in self]


RegisterDiagnosticTypes()


class DiagnosticRef(object):
  def __init__(self, guid):
    self._guid = guid

  @property
  def guid(self):
    return self._guid

  @property
  def has_guid(self):
    return True

  def AsDict(self):
    return self.guid


class UnmergeableDiagnosticSet(Diagnostic):
  def __init__(self, diagnostics):
    super(UnmergeableDiagnosticSet, self).__init__()
    self._diagnostics = diagnostics

  def __len__(self):
    return len(self._diagnostics)

  def __iter__(self):
    for diagnostic in self._diagnostics:
      yield diagnostic

  def CanAddDiagnostic(self, unused_other_diagnostic, unused_name,
                       unused_parent_hist, unused_other_parent_hist):
    return True

  def AddDiagnostic(self, other_diagnostic, name, parent_hist,
                    other_parent_hist):
    if isinstance(other_diagnostic, UnmergeableDiagnosticSet):
      self._diagnostics.extend(other_diagnostic._diagnostics)
      return
    for diagnostic in self:
      if diagnostic.CanAddDiagnostic(other_diagnostic, name, parent_hist,
                                     other_parent_hist):
        diagnostic.AddDiagnostic(other_diagnostic, name, parent_hist,
                                 other_parent_hist)
        return
    self._diagnostics.append(other_diagnostic)

  def _AsDictInto(self, d):
    d['diagnostics'] = [d.AsDictOrReference() for d in self]

  @staticmethod
  def FromDict(dct):
    def RefOrDiagnostic(d):
      if isinstance(d, basestring):
        return DiagnosticRef(d)
      return Diagnostic.FromDict(d)

    return UnmergeableDiagnosticSet(
        [RefOrDiagnostic(d) for d in dct['diagnostics']])


class DiagnosticMap(dict):
  @staticmethod
  def FromDict(dct):
    dm = DiagnosticMap()
    dm.AddDicts(dct)
    return dm

  def AddDicts(self, dct):
    for name, diagnostic_dict in dct.iteritems():
      if isinstance(diagnostic_dict, basestring):
        self[name] = DiagnosticRef(diagnostic_dict)
      else:
        self[name] = Diagnostic.FromDict(diagnostic_dict)

  def ResolveSharedDiagnostics(self, histograms, required=False):
    for name, diagnostic in self.iteritems():
      if not isinstance(diagnostic, DiagnosticRef):
        continue
      guid = diagnostic.guid
      diagnostic = histograms.LookupDiagnostic(guid)
      if isinstance(diagnostic, Diagnostic):
        self[name] = diagnostic
      elif required:
        raise ValueError('Unable to find shared Diagnostic ' + guid)

  def AsDict(self):
    dct = {}
    for name, diagnostic in self.iteritems():
      dct[name] = diagnostic.AsDictOrReference()
    return dct

  def Merge(self, other, parent_hist, other_parent_hist):
    merged_from = self.get(MERGED_FROM_DIAGNOSTIC_KEY)
    if merged_from is None:
      merged_from = RelatedHistogramSet()
      self[MERGED_FROM_DIAGNOSTIC_KEY] = merged_from
    merged_from.Add(other_parent_hist)

    for name, other_diagnostic in other.iteritems():
      if name not in self:
        self[name] = other_diagnostic
        continue
      my_diagnostic = self[name]
      if my_diagnostic.CanAddDiagnostic(
          other_diagnostic, name, parent_hist, other_parent_hist):
        my_diagnostic.AddDiagnostic(
            other_diagnostic, name, parent_hist, other_parent_hist)
        continue
      self[name] = UnmergeableDiagnosticSet([
          my_diagnostic, other_diagnostic])


MAX_DIAGNOSTIC_MAPS = 16


class HistogramBin(object):
  def __init__(self, rang):
    self._range = rang
    self._count = 0
    self._diagnostic_maps = []

  def AddSample(self, unused_x):
    self._count += 1

  @property
  def count(self):
    return self._count

  @property
  def range(self):
    return self._range

  def AddBin(self, other):
    self._count += other.count

  @property
  def diagnostic_maps(self):
    return self._diagnostic_maps

  def AddDiagnosticMap(self, diagnostics):
    UniformlySampleStream(
        self._diagnostic_maps, self.count, diagnostics, MAX_DIAGNOSTIC_MAPS)

  def FromDict(self, dct):
    self._count = dct[0]
    if len(dct) > 1:
      for diagnostic_map_dict in dct[1]:
        self._diagnostic_maps.append(DiagnosticMap.FromDict(
            diagnostic_map_dict))

  def AsDict(self):
    if len(self._diagnostic_maps) == 0:
      return [self.count]
    return [self.count, [d.AsDict() for d in self._diagnostic_maps]]


# TODO(benjhayden): Presubmit to compare with unit.html.
UNIT_NAMES = [
    'ms',
    'tsMs',
    'n%',
    'sizeInBytes',
    'J',
    'W',
    'unitless',
    'count',
    'sigma',
]

def ExtendUnitNames():
  # Use a function in order to avoid cluttering the global namespace with a loop
  # variable.
  for name in list(UNIT_NAMES):
    UNIT_NAMES.append(name + '_biggerIsBetter')
    UNIT_NAMES.append(name + '_smallerIsBetter')

ExtendUnitNames()


class Scalar(object):
  def __init__(self, unit, value):
    assert unit in UNIT_NAMES
    self._unit = unit
    self._value = value

  @property
  def unit(self):
    return self._unit

  @property
  def value(self):
    return self._value

  def AsDict(self):
    return {'type': 'scalar', 'unit': self.unit, 'value': self.value}

  @staticmethod
  def FromDict(dct):
    return Scalar(dct['unit'], dct['value'])


DEFAULT_SUMMARY_OPTIONS = {
    'avg': True,
    'geometricMean': False,
    'std': True,
    'count': True,
    'sum': True,
    'min': True,
    'max': True,
    'nans': False,
    # Don't include 'percentile' here. Its default value is [], which is
    # modifiable. Callers may push to it, so there must be a different Array
    # instance for each Histogram instance.
}


class Histogram(object):
  def __init__(self, name, unit, bin_boundaries=None):
    assert unit in UNIT_NAMES

    if bin_boundaries is None:
      bin_boundaries = DEFAULT_BOUNDARIES_FOR_UNIT[unit]

    self._guid = None

    self._bin_boundaries_dict = bin_boundaries.AsDict()

    self._bins = []
    self._description = ''
    self._name = name
    self._diagnostics = DiagnosticMap()
    self._nan_diagnostic_maps = []
    self._num_nans = 0
    self._running = None
    self._sample_values = []
    self._short_name = None
    self._summary_options = dict(DEFAULT_SUMMARY_OPTIONS)
    self._summary_options['percentile'] = []
    self._unit = unit

    for rang in bin_boundaries.bin_ranges:
      self._bins.append(HistogramBin(rang))

    self._max_num_sample_values = self._GetDefaultMaxNumSampleValues()

  @property
  def nan_diagnostic_maps(self):
    return self._nan_diagnostic_maps

  @property
  def unit(self):
    return self._unit

  @property
  def running(self):
    return self._running

  @property
  def max_num_sample_values(self):
    return self._max_num_sample_values

  @max_num_sample_values.setter
  def max_num_sample_values(self, n):
    self._max_num_sample_values = n
    UniformlySampleArray(self._sample_values, self._max_num_sample_values)

  @property
  def sample_values(self):
    return self._sample_values

  @property
  def name(self):
    return self._name

  @property
  def short_name(self):
    return self._short_name

  @property
  def guid(self):
    if self._guid is None:
      self._guid = str(uuid.uuid4())
    return self._guid

  @guid.setter
  def guid(self, g):
    assert self._guid is None
    self._guid = g

  @property
  def bins(self):
    return self._bins

  @property
  def diagnostics(self):
    return self._diagnostics

  @staticmethod
  def FromDict(dct):
    boundaries = HistogramBinBoundaries.FromDict(dct.get('binBoundaries'))
    hist = Histogram(dct['name'], dct['unit'], boundaries)
    hist.guid = dct['guid']
    if 'shortName' in dct:
      hist._short_name = dct['shortName']
    if 'description' in dct:
      hist._description = dct['description']
    if 'diagnostics' in dct:
      hist._diagnostics.AddDicts(dct['diagnostics'])
    if 'allBins' in dct:
      if isinstance(dct['allBins'], list):
        for i, bin_dct in enumerate(dct['allBins']):
          hist._bins[i].FromDict(bin_dct)
      else:
        for i, bin_dct in dct['allBins'].iteritems():
          hist._bins[int(i)].FromDict(bin_dct)
    if 'running' in dct:
      hist._running = RunningStatistics.FromDict(dct['running'])
    if 'summaryOptions' in dct:
      hist.CustomizeSummaryOptions(dct['summaryOptions'])
    if 'maxNumSampleValues' in dct:
      hist._max_num_sample_values = dct['maxNumSampleValues']
    if 'sampleValues' in dct:
      hist._sample_values = dct['sampleValues']
    if 'numNans' in dct:
      hist._num_nans = dct['numNans']
    if 'nanDiagnostics' in dct:
      for map_dct in dct['nanDiagnostics']:
        hist._nan_diagnostic_maps.append(DiagnosticMap.FromDict(map_dct))
    return hist

  @property
  def num_values(self):
    if self._running is None:
      return 0
    return self._running.count

  @property
  def num_nans(self):
    return self._num_nans

  @property
  def average(self):
    if self._running is None:
      return None
    return self._running.mean

  @property
  def standard_deviation(self):
    if self._running is None:
      return None
    return self._running.stddev

  @property
  def geometric_mean(self):
    if self._running is None:
      return 0
    return self._running.geometric_mean

  @property
  def sum(self):
    if self._running is None:
      return 0
    return self._running.sum

  def GetApproximatePercentile(self, percent):
    if percent < 0 or percent > 1:
      raise ValueError('percent must be in [0,1]')
    if self.num_values == 0:
      return 0

    if len(self._bins) == 1:
      sorted_sample_values = list(self._sample_values)
      sorted_sample_values.sort()
      return sorted_sample_values[
          int((len(sorted_sample_values) - 1) * percent)]

    values_to_skip = math.floor((self.num_values - 1) * percent)
    for hbin in self._bins:
      values_to_skip -= hbin.count
      if values_to_skip >= 0:
        continue
      if hbin.range.min == -JS_MAX_VALUE:
        return hbin.range.max
      elif hbin.range.max == JS_MAX_VALUE:
        return hbin.range.min
      else:
        return hbin.range.center
    return self._bins[len(self._bins) - 1].range.min

  def GetBinForValue(self, value):
    index = FindHighIndexInSortedArray(
        self._bins, lambda b: (-1 if (value < b.range.max) else 1))
    if 0 <= index < len(self._bins):
      return self._bins[index]
    return self._bins[len(self._bins) - 1]

  def AddSample(self, value, diagnostic_map=None):
    if (diagnostic_map is not None and
        not isinstance(diagnostic_map, DiagnosticMap)):
      diagnostic_map = DiagnosticMap(diagnostic_map)

    if not isinstance(value, (int, float)) or math.isnan(value):
      self._num_nans += 1
      if diagnostic_map:
        UniformlySampleStream(self._nan_diagnostic_maps, self.num_nans,
                              diagnostic_map, MAX_DIAGNOSTIC_MAPS)
    else:
      if self._running is None:
        self._running = RunningStatistics()
      self._running.Add(value)

      hbin = self.GetBinForValue(value)
      hbin.AddSample(value)
      if diagnostic_map:
        hbin.AddDiagnosticMap(diagnostic_map)

    UniformlySampleStream(self._sample_values, self.num_values + self.num_nans,
                          value, self.max_num_sample_values)

  def CanAddHistogram(self, other):
    if self.unit != other.unit:
      return False
    return self._bin_boundaries_dict == other._bin_boundaries_dict

  def AddHistogram(self, other):
    if not self.CanAddHistogram(other):
      raise ValueError('Merging incompatible Histograms')

    MergeSampledStreams(
        self.sample_values, self.num_values,
        other.sample_values, other.num_values,
        (self.max_num_sample_values + other.max_num_sample_values) / 2)
    self._num_nans += other._num_nans

    if other.running is not None:
      if self.running is None:
        self._running = RunningStatistics()
      self._running = self._running.Merge(other.running)

    for i, hbin in enumerate(other.bins):
      self.bins[i].AddBin(hbin)

    self.diagnostics.Merge(other.diagnostics, self, other)

  def CustomizeSummaryOptions(self, options):
    for key, value in options.iteritems():
      self._summary_options[key] = value

  def Clone(self):
    return Histogram.FromDict(self.AsDict())

  def CloneEmpty(self):
    return Histogram(self.name, self.unit, HistogramBinBoundaries.FromDict(
        self._bin_boundaries_dict))

  @property
  def statistics_scalars(self):
    results = {}
    for stat_name, option in self._summary_options.iteritems():
      if not option:
        continue
      if stat_name == 'percentile':
        for percent in option:
          percentile = self.GetApproximatePercentile(percent)
          results['pct_' + PercentToString(percent)] = Scalar(
              self.unit, percentile)
      elif stat_name == 'nans':
        results['nans'] = Scalar('count', self.num_nans)
      else:
        if stat_name == 'count':
          stat_unit = 'count'
        else:
          stat_unit = self.unit
        if stat_name == 'std':
          key = 'stddev'
        elif stat_name == 'avg':
          key = 'mean'
        elif stat_name == 'geometricMean':
          key = 'geometric_mean'
        else:
          key = stat_name
        if self._running is None:
          self._running = RunningStatistics()
        stat_value = getattr(self._running, key)
        if isinstance(stat_value, (int, float)):
          results[stat_name] = Scalar(stat_unit, stat_value)
    return results

  def AsDict(self):
    dct = {'name': self.name, 'unit': self.unit, 'guid': self.guid}
    if self._bin_boundaries_dict is not None:
      dct['binBoundaries'] = self._bin_boundaries_dict
    if self._short_name:
      dct['shortName'] = self._short_name
    if self._description:
      dct['description'] = self._description
    if len(self.diagnostics):
      dct['diagnostics'] = self.diagnostics.AsDict()
    if self.max_num_sample_values != self._GetDefaultMaxNumSampleValues():
      dct['maxNumSampleValues'] = self.max_num_sample_values
    if self.num_nans:
      dct['numNans'] = self.num_nans
    if len(self.nan_diagnostic_maps):
      dct['nanDiagnostics'] = [m.AsDict() for m in self.nan_diagnostic_maps]
    if self.num_values:
      dct['sampleValues'] = list(self.sample_values)
      dct['running'] = self._running.AsDict()
      dct['allBins'] = self._GetAllBinsAsDict()
      if dct['allBins'] is None:
        del dct['allBins']

    summary_options = {}
    any_overridden_summary_options = False
    for name, option in self._summary_options.iteritems():
      if name == 'percentile':
        if len(option) == 0:
          continue
      elif option == DEFAULT_SUMMARY_OPTIONS[name]:
        continue
      summary_options[name] = option
      any_overridden_summary_options = True
    if any_overridden_summary_options:
      dct['summaryOptions'] = summary_options
    return dct

  def _GetAllBinsAsDict(self):
    num_bins = len(self._bins)
    empty_bins = 0
    for hbin in self._bins:
      if hbin.count == 0:
        empty_bins += 1
    if empty_bins == num_bins:
      return None

    if empty_bins > (num_bins / 2):
      all_bins_dict = {}
      for i, hbin in enumerate(self._bins):
        if hbin.count > 0:
          all_bins_dict[i] = hbin.AsDict()
      return all_bins_dict

    all_bins_list = []
    for hbin in self._bins:
      all_bins_list.append(hbin.AsDict())
    return all_bins_list

  def _GetDefaultMaxNumSampleValues(self):
    return len(self._bins) * 10


class HistogramBinBoundaries(object):
  CACHE = {}
  SLICE_TYPE_LINEAR = 0
  SLICE_TYPE_EXPONENTIAL = 1

  def __init__(self, min_bin_boundary):
    self._builder = [min_bin_boundary]
    self._range = Range()
    self._range.AddValue(min_bin_boundary)
    self._bin_ranges = None

  @property
  def range(self):
    return self._range

  @staticmethod
  def FromDict(dct):
    if dct is None:
      return HistogramBinBoundaries.SINGULAR

    cache_key = json.dumps(dct)
    if cache_key in HistogramBinBoundaries.CACHE:
      return HistogramBinBoundaries.CACHE[cache_key]

    bin_boundaries = HistogramBinBoundaries(dct[0])
    for slic in dct[1:]:
      if not isinstance(slic, list):
        bin_boundaries.AddBinBoundary(slic)
        continue
      if slic[0] == HistogramBinBoundaries.SLICE_TYPE_LINEAR:
        bin_boundaries.AddLinearBins(slic[1], slic[2])
      elif slic[0] == HistogramBinBoundaries.SLICE_TYPE_EXPONENTIAL:
        bin_boundaries.AddExponentialBins(slic[1], slic[2])
      else:
        raise ValueError('Unrecognized HistogramBinBoundaries slice type')

    HistogramBinBoundaries.CACHE[cache_key] = bin_boundaries
    return bin_boundaries

  def AsDict(self):
    if len(self._builder) == 1 and self._builder[0] == JS_MAX_VALUE:
      return None
    return self._builder

  @staticmethod
  def CreateExponential(lower, upper, num_bins):
    return HistogramBinBoundaries(lower).AddExponentialBins(upper, num_bins)

  @staticmethod
  def CreateLinear(lower, upper, num_bins):
    return HistogramBinBoundaries(lower).AddLinearBins(upper, num_bins)

  def _PushBuilderSlice(self, slic):
    self._builder += [slic]

  def AddBinBoundary(self, next_max_bin_boundary):
    if next_max_bin_boundary <= self.range.max:
      raise ValueError('The added max bin boundary must be larger than ' +
                       'the current max boundary')
    self._bin_ranges = None
    self._PushBuilderSlice(next_max_bin_boundary)
    self.range.AddValue(next_max_bin_boundary)
    return self

  def AddLinearBins(self, next_max_bin_boundary, bin_count):
    if bin_count <= 0:
      raise ValueError('Bin count must be positive')
    if next_max_bin_boundary <= self.range.max:
      raise ValueError('The new max bin boundary must be greater than ' +
                       'the previous max bin boundary')

    self._bin_ranges = None
    self._PushBuilderSlice([
        HistogramBinBoundaries.SLICE_TYPE_LINEAR,
        next_max_bin_boundary, bin_count])
    self.range.AddValue(next_max_bin_boundary)
    return self

  def AddExponentialBins(self, next_max_bin_boundary, bin_count):
    if bin_count <= 0:
      raise ValueError('Bin count must be positive')
    if self.range.max <= 0:
      raise ValueError('Current max bin boundary must be positive')
    if self.range.max >= next_max_bin_boundary:
      raise ValueError('The last added max boundary must be greater than ' +
                       'the current max boundary boundary')

    self._bin_ranges = None

    self._PushBuilderSlice([
        HistogramBinBoundaries.SLICE_TYPE_EXPONENTIAL,
        next_max_bin_boundary, bin_count])
    self.range.AddValue(next_max_bin_boundary)
    return self

  @property
  def bin_ranges(self):
    if self._bin_ranges is None:
      self._Build()
    return self._bin_ranges

  def _Build(self):
    if not isinstance(self._builder[0], (int, float)):
      raise ValueError('Invalid start of builder_')

    self._bin_ranges = []
    prev_boundary = self._builder[0]
    if prev_boundary > -JS_MAX_VALUE:
      # underflow bin
      self._bin_ranges.append(Range.FromExplicitRange(
          -JS_MAX_VALUE, prev_boundary))

    for slic in self._builder[1:]:
      if not isinstance(slic, list):
        self._bin_ranges.append(Range.FromExplicitRange(
            prev_boundary, slic))
        prev_boundary = slic
        continue

      next_max_bin_boundary = float(slic[1])
      bin_count = slic[2]
      slice_min_bin_boundary = float(prev_boundary)

      if slic[0] == self.SLICE_TYPE_LINEAR:
        bin_width = (next_max_bin_boundary - prev_boundary) / bin_count
        for i in xrange(1, bin_count):
          boundary = slice_min_bin_boundary + (i * bin_width)
          self._bin_ranges.append(Range.FromExplicitRange(
              prev_boundary, boundary))
          prev_boundary = boundary
      elif slic[0] == self.SLICE_TYPE_EXPONENTIAL:
        bin_exponent_width = (
            math.log(next_max_bin_boundary / prev_boundary) / bin_count)
        for i in xrange(1, bin_count):
          boundary = slice_min_bin_boundary * math.exp(i * bin_exponent_width)
          self._bin_ranges.append(Range.FromExplicitRange(
              prev_boundary, boundary))
          prev_boundary = boundary
      else:
        raise ValueError('Unrecognized HistogramBinBoundaries slice type')

      self._bin_ranges.append(Range.FromExplicitRange(
          prev_boundary, next_max_bin_boundary))
      prev_boundary = next_max_bin_boundary

    if prev_boundary < JS_MAX_VALUE:
      # overflow bin
      self._bin_ranges.append(Range.FromExplicitRange(
          prev_boundary, JS_MAX_VALUE))


HistogramBinBoundaries.SINGULAR = HistogramBinBoundaries(JS_MAX_VALUE)


DEFAULT_BOUNDARIES_FOR_UNIT = {
    'ms': HistogramBinBoundaries.CreateExponential(1e-3, 1e6, 1e2),
    'tsMs': HistogramBinBoundaries.CreateLinear(0, 1e10, 1e3),
    'n%': HistogramBinBoundaries.CreateLinear(0, 1.0, 20),
    'sizeInBytes': HistogramBinBoundaries.CreateExponential(1, 1e12, 1e2),
    'J': HistogramBinBoundaries.CreateExponential(1e-3, 1e3, 50),
    'W': HistogramBinBoundaries.CreateExponential(1e-3, 1, 50),
    'unitless': HistogramBinBoundaries.CreateExponential(1e-3, 1e3, 50),
    'count': HistogramBinBoundaries.CreateExponential(1, 1e3, 20),
    'sigma': HistogramBinBoundaries.CreateLinear(-5, 5, 50),
}
