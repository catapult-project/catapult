# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict

from telemetry.value import failure
from telemetry.value import merge_values

class Summary(object):
  """Computes summary values from the per-page-run values produced by a test.

  Some telemetry benchmark repeat a number of times in order to get a reliable
  measurement. The test does not have to handle merging of these runs:
  summarizer does it for you.

  For instance, if two pages run, 3 and 1 time respectively:
      ScalarValue(page1, 'foo', units='ms', 1)
      ScalarValue(page1, 'foo', units='ms', 1)
      ScalarValue(page1, 'foo', units='ms', 1)
      ScalarValue(page2, 'foo', units='ms', 2)

  Then summarizer will produce two sets of values. First,
  computed_per_page_values:
      [
         ListOfScalarValues(page1, 'foo', units='ms', [1,1,1])],
         ListOfScalarValues(page2, 'foo', units='ms', [2])]
      ]

  In addition, it will produce a summary value:
      [
         ListOfScalarValues(page=None, 'foo', units='ms', [1,1,1,2])]
      ]

  """
  def __init__(self, all_page_specific_values, had_failures):
    self.had_failures = had_failures
    self._computed_per_page_values = []
    self._computed_summary_values = []
    self._interleaved_computed_per_page_values_and_summaries = []
    self._ComputePerPageValues(all_page_specific_values)

  @property
  def computed_per_page_values(self):
    return self._computed_per_page_values

  @property
  def computed_summary_values(self):
    return self._computed_summary_values

  @property
  def interleaved_computed_per_page_values_and_summaries(self):
    """Returns the computed per page values and summary values interleaved.

    All the results for a given name are printed together. First per page
    values, then summary values.

    """
    return self._interleaved_computed_per_page_values_and_summaries

  def _ComputePerPageValues(self, all_page_specific_values):
    all_successful_page_values = [
        v for v in all_page_specific_values if not isinstance(
            v, failure.FailureValue)]

    # We will later need to determine how many values were originally created
    # for each value name, to apply a workaround meant to clean up the printf
    # output.
    num_successful_pages_for_value_name = defaultdict(int)
    for v in all_successful_page_values:
      num_successful_pages_for_value_name[v.name] += 1

    # By here, due to page repeat options, all_values_from_successful_pages
    # contains values of the same name not only from mulitple pages, but also
    # from the same name. So even if, for instance, only one page ran, it may
    # have run twice, producing two 'x' values.
    #
    # So, get rid of the repeated pages by merging.
    merged_page_values = merge_values.MergeLikeValuesFromSamePage(
        all_successful_page_values)

    # Now we have a bunch of values, but there is only one value_name per page.
    # Suppose page1 and page2 ran, producing values x and y. We want to print
    #    x for page1
    #    x for page2
    #    x for page1, page2 combined
    #
    #    y for page1
    #    y for page2
    #    y for page1, page2 combined
    #
    # We already have the x values in the values array. But, we will need
    # them indexable by the value name.
    #
    # The following dict maps value_name -> list of pages that have values of
    # that name.
    per_page_values_by_value_name = defaultdict(list)
    for value in merged_page_values:
      per_page_values_by_value_name[value.name].append(value)

    # We already have the x values in the values array. But, we also need
    # the values merged across the pages. And, we will need them indexed by
    # value name so that we can find them when printing out value names in
    # alphabetical order.
    merged_pages_value_by_value_name = {}
    if not self.had_failures:
      for value in merge_values.MergeLikeValuesFromDifferentPages(
          all_successful_page_values):
        assert value.name not in merged_pages_value_by_value_name
        merged_pages_value_by_value_name[value.name] = value

    # sorted_value names will govern the order we start printing values.
    value_names = set([v.name for v in merged_page_values])
    sorted_value_names = sorted(value_names)

    # Time to walk through the values by name, printing first the page-specific
    # values and then the merged_site value.
    for value_name in sorted_value_names:
      per_page_values = per_page_values_by_value_name.get(value_name, [])

      # Sort the values by their url
      sorted_per_page_values = list(per_page_values)
      sorted_per_page_values.sort(
          key=lambda per_page_values: per_page_values.page.display_name)

      # Output the page-specific results.
      num_successful_pages_for_this_value_name = (
          num_successful_pages_for_value_name[value_name])
      for per_page_value in sorted_per_page_values:
        self._ComputePerPageValue(per_page_value,
                                  num_successful_pages_for_this_value_name)

      # Output the combined values.
      merged_pages_value = merged_pages_value_by_value_name.get(value_name,
                                                                None)
      if merged_pages_value:
        self._computed_summary_values.append(merged_pages_value)
        self._interleaved_computed_per_page_values_and_summaries.append(
            merged_pages_value)

  def _ComputePerPageValue(
      self, value, num_successful_pages_for_this_value_name):
    # If there were any page errors, we typically will print nothing.
    #
    # Note: this branch is structured less-densely to improve legibility.
    if num_successful_pages_for_this_value_name > 1:
      should_print = True
    elif (self.had_failures and
         num_successful_pages_for_this_value_name == 1):
      should_print = True
    else:
      should_print = False

    if not should_print:
      return

    # Actually save the result.
    self._computed_per_page_values.append(value)
    self._interleaved_computed_per_page_values_and_summaries.append(value)
