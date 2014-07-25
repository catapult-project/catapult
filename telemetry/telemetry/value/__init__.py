# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""
The Value hierarchy provides a way of representing the values measurements
produce such that they can be merged across runs, grouped by page, and output
to different targets.

The core Value concept provides the basic functionality:
- association with a page, may be none
- naming and units
- importance tracking [whether a value will show up on a waterfall or output
  file by default]
- other metadata, such as a description of what was measured
- default conversion to scalar and string
- merging properties

A page may actually run a few times during a single telemetry session.
Downstream consumers of test results typically want to group these runs
together, then compute summary statistics across runs. Value provides the
Merge* family of methods for this kind of aggregation.
"""

# When combining a pair of Values togehter, it is sometimes ambiguous whether
# the values should be concatenated, or one should be picked as representative.
# The possible merging policies are listed here.
CONCATENATE = 'concatenate'
PICK_FIRST = 'pick-first'

# When converting a Value to its buildbot equivalent, the context in which the
# value is being interpreted actually affects the conversion. This is insane,
# but there you have it. There are three contexts in which Values are converted
# for use by buildbot, represented by these output-intent values.
PER_PAGE_RESULT_OUTPUT_CONTEXT = 'per-page-result-output-context'
COMPUTED_PER_PAGE_SUMMARY_OUTPUT_CONTEXT = 'merged-pages-result-output-context'
SUMMARY_RESULT_OUTPUT_CONTEXT = 'summary-result-output-context'

class Value(object):
  """An abstract value produced by a telemetry page test.
  """
  def __init__(self, page, name, units, important, description):
    """A generic Value object.

    Args:
      page: A Page object, may be given as None to indicate that the value
          represents results for multiple pages.
      name: A value name string, may contain a dot. Values from the same test
          with the same prefix before the dot may be considered to belong to
          the same chart.
      units: A units string.
      important: Whether the value is "important". Causes the value to appear
          by default in downstream UIs.
      description: A string explaining in human-understandable terms what this
          value represents.
    """
    self.page = page
    self.name = name
    self.units = units
    self.important = important
    self.description = description

  def IsMergableWith(self, that):
    return (self.units == that.units and
            type(self) == type(that) and
            self.important == that.important)

  @classmethod
  def MergeLikeValuesFromSamePage(cls, values):
    """Combines the provided list of values into a single compound value.

    When a page runs multiple times, it may produce multiple values. This
    function is given the same-named values across the multiple runs, and has
    the responsibility of producing a single result.

    It must return a single Value. If merging does not make sense, the
    implementation must pick a representative value from one of the runs.

    For instance, it may be given
        [ScalarValue(page, 'a', 1), ScalarValue(page, 'a', 2)]
    and it might produce
        ListOfScalarValues(page, 'a', [1, 2])
    """
    raise NotImplementedError()

  @classmethod
  def MergeLikeValuesFromDifferentPages(cls, values,
                                        group_by_name_suffix=False):
    """Combines the provided values into a single compound value.

    When a full pageset runs, a single value_name will usually end up getting
    collected for multiple pages. For instance, we may end up with
       [ScalarValue(page1, 'a',  1),
        ScalarValue(page2, 'a',  2)]

    This function takes in the values of the same name, but across multiple
    pages, and produces a single summary result value. In this instance, it
    could produce a ScalarValue(None, 'a', 1.5) to indicate averaging, or even
    ListOfScalarValues(None, 'a', [1, 2]) if concatenated output was desired.

    Some results are so specific to a page that they make no sense when
    aggregated across pages. If merging values of this type across pages is
    non-sensical, this method may return None.

    If group_by_name_suffix is True, then x.z and y.z are considered to be the
    same value and are grouped together. If false, then x.z and y.z are
    considered different.
    """
    raise NotImplementedError()

  def _IsImportantGivenOutputIntent(self, output_context):
    if output_context == PER_PAGE_RESULT_OUTPUT_CONTEXT:
      return False
    elif output_context == COMPUTED_PER_PAGE_SUMMARY_OUTPUT_CONTEXT:
      return self.important
    elif output_context == SUMMARY_RESULT_OUTPUT_CONTEXT:
      return self.important

  def GetBuildbotDataType(self, output_context):
    """Returns the buildbot's equivalent data_type.

    This should be one of the values accepted by perf_tests_results_helper.py.
    """
    raise NotImplementedError()

  def GetBuildbotValue(self):
    """Returns the buildbot's equivalent value."""
    raise NotImplementedError()

  def GetBuildbotMeasurementAndTraceNameForPerPageResult(self):
    measurement, _ = _ConvertValueNameToBuildbotChartAndTraceName(self.name)
    return measurement, self.page.display_name

  @property
  def name_suffix(self):
    """Returns the string after a . in the name, or the full name otherwise."""
    if '.' in self.name:
      return self.name.split('.', 1)[1]
    else:
      return self.name

  def GetBuildbotMeasurementAndTraceNameForComputedSummaryResult(
      self, trace_tag):
    measurement, bb_trace_name = (
        _ConvertValueNameToBuildbotChartAndTraceName(self.name))
    if trace_tag:
      return measurement, bb_trace_name + trace_tag
    else:
      return measurement, bb_trace_name

  def GetRepresentativeNumber(self):
    """Gets a single scalar value that best-represents this value.

    Returns None if not possible.
    """
    raise NotImplementedError()

  def GetRepresentativeString(self):
    """Gets a string value that best-represents this value.

    Returns None if not possible.
    """
    raise NotImplementedError()

  @classmethod
  def GetJSONTypeName(cls):
    """Gets the typename for serialization to JSON using AsDict."""
    raise NotImplementedError()

  def AsDict(self):
    """Gets a representation of this value as a dict for eventual
    serialization to JSON.
    """
    return self._AsDictImpl()

  def _AsDictImpl(self):
    d = {
      'name': self.name,
      'type': self.GetJSONTypeName(),
      'unit': self.units,
    }

    if self.description:
      d['description'] = self.description

    if self.page:
      d['page_id'] = self.page.id

    return d

  def AsDictWithoutBaseClassEntries(self):
    full_dict = self.AsDict()
    base_dict_keys = set(self._AsDictImpl().keys())

    # Extracts only entries added by the subclass.
    return dict([(k, v) for (k, v) in full_dict.iteritems()
                  if k not in base_dict_keys])

def ValueNameFromTraceAndChartName(trace_name, chart_name=None):
  """Mangles a trace name plus optional chart name into a standard string.

  A value might just be a bareword name, e.g. numPixels. In that case, its
  chart may be None.

  But, a value might also be intended for display with other values, in which
  case the chart name indicates that grouping. So, you might have
  screen.numPixels, screen.resolution, where chartName='screen'.
  """
  assert trace_name != 'url', 'The name url cannot be used'
  if chart_name:
    return '%s.%s' % (chart_name, trace_name)
  else:
    assert '.' not in trace_name, ('Trace names cannot contain "." with an '
        'empty chart_name since this is used to delimit chart_name.trace_name.')
    return trace_name

def _ConvertValueNameToBuildbotChartAndTraceName(value_name):
  """Converts a value_name into the buildbot equivalent name pair.

  Buildbot represents values by the measurement name and an optional trace name,
  whereas telemetry represents values with a chart_name.trace_name convention,
  where chart_name is optional.

  This converts from the telemetry convention to the buildbot convention,
  returning a 2-tuple (measurement_name, trace_name).
  """
  if '.' in value_name:
    return value_name.split('.', 1)
  else:
    return value_name, value_name
