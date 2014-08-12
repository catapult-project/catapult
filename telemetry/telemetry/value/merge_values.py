# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.value import failure
from telemetry.value import skip


def MergeLikeValuesFromSamePage(all_values):
  """Merges values that measure the same thing on the same page.

  A page may end up being measured multiple times, meaning that we may end up
  with something like this:
       ScalarValue(page1, 'x', 1)
       ScalarValue(page2, 'x', 4)
       ScalarValue(page1, 'x', 2)
       ScalarValue(page2, 'x', 5)

  This function will produce:
       ListOfScalarValues(page1, 'x', [1, 2])
       ListOfScalarValues(page2, 'x', [4, 5])

  The workhorse of this code is Value.MergeLikeValuesFromSamePage.

  This requires (but assumes) that the values passed in with the same grouping
  key pass the Value.IsMergableWith test. If this is not obeyed, the
  results will be undefined.
  """
  return _MergeLikeValuesCommon(
      all_values,
      lambda x: (x.page, x.name),
      lambda v0, merge_group: v0.MergeLikeValuesFromSamePage(merge_group))


def MergeLikeValuesFromDifferentPages(all_values, group_by_name_suffix=False):
  """Merges values that measure the same thing on different pages.

  After using MergeLikeValuesFromSamePage, one still ends up with values from
  different pages:
       ScalarValue(page1, 'x', 1)
       ScalarValue(page1, 'y', 30)
       ScalarValue(page2, 'x', 2)
       ScalarValue(page2, 'y', 40)

  This function will group the values of the same value_name together:
       ListOfScalarValues(None, 'x', [1, 2])
       ListOfScalarValues(None, 'y', [30, 40])

  If group_by_name_suffix is True, then x.z and y.z are considered to be the
  same value and are grouped together. If false, then x.z and y.z are
  considered different.

  The workhorse of this code is Value.MergeLikeValuesFromDifferentPages.

  Not all values that go into this function will come out: not every value can
  be merged across pages. Values whose MergeLikeValuesFromDifferentPages returns
  None will be omitted from the results.

  This requires (but assumes) that the values passed in with the same name pass
  the Value.IsMergableWith test. If this is not obeyed, the results
  will be undefined.
  """
  if group_by_name_suffix:
    def key(value):
      return value.name_suffix
  else:
    key = lambda x: x.name
  return _MergeLikeValuesCommon(
      all_values,
      key,
      lambda v0, merge_group: v0.MergeLikeValuesFromDifferentPages(
          merge_group, group_by_name_suffix=group_by_name_suffix))


def _MergeLikeValuesCommon(all_values, key_func, merge_func):
  """Groups all_values by key_func then applies merge_func to the groups.

  This takes the all_values list and groups each item in that using the key
  provided by key_func. This produces groups of values with like keys. Thes are
  then handed to the merge_func to produce a new key. If merge_func produces a
  non-None return, it is added to the list of returned values.
  """
  # When merging, we want to merge values in a consistent order, e.g. so that
  # Scalar(1), Scalar(2) predictably produces ListOfScalarValues([1,2]) rather
  # than 2,1.
  #
  # To do this, the values are sorted by key up front. Then, grouping is
  # performed using a dictionary, but as new groups are found, the order in
  # which they were found is also noted.
  #
  # Merging is then performed on groups in group-creation-order. This ensures
  # that the returned array is in a stable order, group by group.
  #
  # Within a group, the order is stable because of the original sort.
  all_values = list(all_values)
  merge_groups = GroupStably(all_values, key_func)

  res = []
  for merge_group in merge_groups:
    v0 = merge_group[0]
    vM = merge_func(v0, merge_group)
    if vM:
      res.append(vM)
  return res

def GroupStably(all_values, key_func):
  """Groups an array by key_func, with the groups returned in a stable order.

  Returns a list of groups.
  """
  all_values = list(all_values)

  merge_groups = {}
  merge_groups_in_creation_order = []
  for value in all_values:
    # TODO(chrishenry): This is temporary. When we figure out the
    # right summarization strategy for page runs with failures/skips, we
    # should use that instead.
    should_skip_value = (isinstance(value, failure.FailureValue) or
                         isinstance(value, skip.SkipValue))

    if should_skip_value:
      continue

    key = key_func(value)
    if key not in merge_groups:
      merge_groups[key] = []
      merge_groups_in_creation_order.append(merge_groups[key])
    merge_groups[key].append(value)
  return merge_groups_in_creation_order
