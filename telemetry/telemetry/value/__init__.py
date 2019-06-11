# Copyright 2014 The Chromium Authors. All rights reserved.
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
import os

from telemetry.core import util

from py_utils import discover


class Value(object):
  """An abstract value produced by a telemetry page test.
  """
  def __init__(self, page, name, units, important, description,
               tir_label, grouping_keys):
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
      tir_label: The string label of the TimelineInteractionRecord with
          which this value is associated.
      grouping_keys: A dict that maps grouping key names to grouping keys.
    """
    # TODO(eakuefner): Check story here after migration (crbug.com/442036)
    if not isinstance(name, basestring):
      raise ValueError('name field of Value must be string.')
    if not isinstance(units, basestring):
      raise ValueError('units field of Value must be string.')
    if not isinstance(important, bool):
      raise ValueError('important field of Value must be bool.')
    if not ((description is None) or isinstance(description, basestring)):
      raise ValueError('description field of Value must absent or string.')
    if not ((tir_label is None) or
            isinstance(tir_label, basestring)):
      raise ValueError('tir_label field of Value must absent or '
                       'string.')
    if not ((grouping_keys is None) or isinstance(grouping_keys, dict)):
      raise ValueError('grouping_keys field of Value must be absent or dict')

    if grouping_keys is None:
      grouping_keys = {}

    self.page = page
    self.name = name
    self.units = units
    self.important = important
    self.description = description
    self.tir_label = tir_label
    self.grouping_keys = grouping_keys

  def __eq__(self, other):
    return hash(self) == hash(other)

  def __hash__(self):
    return hash(str(self))

  def IsMergableWith(self, that):
    # pylint: disable=unidiomatic-typecheck
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
  def MergeLikeValuesFromDifferentPages(cls, values):
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
    """
    raise NotImplementedError()

  @staticmethod
  def GetJSONTypeName():
    """Gets the typename for serialization to JSON using AsDict."""
    raise NotImplementedError()

  def AsDict(self):
    """Pre-serializes a value to a dict for output as JSON."""
    return self._AsDictImpl()

  def _AsDictImpl(self):
    d = {
        'name': self.name,
        'type': self.GetJSONTypeName(),
        'units': self.units,
        'important': self.important
    }

    if self.description:
      d['description'] = self.description

    if self.tir_label:
      d['tir_label'] = self.tir_label

    if self.page:
      d['page_id'] = self.page.id

    if self.grouping_keys:
      d['grouping_keys'] = self.grouping_keys

    return d


def MergedTirLabel(values):
  """Returns the tir_label that should be applied to a merge of values.

  As of TBMv2, we encounter situations where we need to merge values with
  different tir_labels because Telemetry's tir_label field is being used to
  store story keys for system health stories. As such, when merging, we want to
  take the common tir_label if all values share the same label (legacy
  behavior), or have no tir_label if not.

  Args:
    values: a list of Value instances

  Returns:
    The tir_label that would be set on the merge of |values|.
  """
  assert len(values) > 0
  v0 = values[0]

  first_tir_label = v0.tir_label
  if all(v.tir_label == first_tir_label for v in values):
    return first_tir_label
  else:
    return None
