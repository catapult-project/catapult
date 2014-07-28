# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import csv

from telemetry.results import output_formatter
from telemetry.value import merge_values


class CsvOutputFormatter(output_formatter.OutputFormatter):
  def __init__(self, output_stream):
    super(CsvOutputFormatter, self).__init__(output_stream)

  def Format(self, page_test_results):
    values = merge_values.MergeLikeValuesFromSamePage(
        page_test_results.all_page_specific_values)
    writer = csv.writer(self.output_stream)
    header_value_names = self._OutputHeader(values, writer)
    value_groups_by_page = merge_values.GroupStably(
        values, lambda value: value.page.url)
    for values_for_page in value_groups_by_page:
      self._OutputValuesForPage(
          header_value_names, values_for_page[0].page, values_for_page,
          writer)

  def _OutputHeader(self, values, csv_writer):
    """Output the header rows.

    This will retrieve the header string from the given values. As a
    results, you would typically pass it all of the recorded values at
    the end of the entire telemetry run. In cases where each page
    produces the same set of value names, you may call this method
    with that set of values.

    Args:
      values: A set of values from which to extract the header string,
          which is the value name and the units.
      writer: A csv.writer instance.

    Returns:
      The value names being output on the header, in the order of
      output.
    """
    representative_values = {}
    for value in values:
      if value.name not in representative_values:
        representative_values[value.name] = value
    header_value_names = list(representative_values.keys())
    header_value_names.sort()

    row = ['page_name']
    for value_name in header_value_names:
      units = representative_values[value_name].units
      row.append('%s (%s)' % (value_name, units))
    csv_writer.writerow(row)
    self.output_stream.flush()
    return header_value_names

  def _OutputValuesForPage(self, header_value_names, page, page_values,
                           csv_writer):
    row = [page.display_name]
    values_by_value_name = {}
    for value in page_values:
      values_by_value_name[value.name] = value

    for value_name in header_value_names:
      value = values_by_value_name.get(value_name, None)
      if value and value.GetRepresentativeNumber():
        row.append('%s' % value.GetRepresentativeNumber())
      else:
        row.append('-')
    csv_writer.writerow(row)
    self.output_stream.flush()
