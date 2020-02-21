# Copyright (c) 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import math

import apache_beam as beam

## Copy of dashboard.common.utils.TestPath for google.cloud.datastore.key.Key
## rather than ndb.Key.
def TestPath(key):
  if key.kind == 'Test':
    # The Test key looks like ('Master', 'name', 'Bot', 'name', 'Test' 'name'..)
    # Pull out every other entry and join with '/' to form the path.
    return '/'.join(key.flat_path[1::2])
  assert key.kind == 'TestMetadata' or key.kind == 'TestContainer'
  return key.name


def FloatHack(f):
  """Workaround BQ streaming inserts not supporting inf and NaN values.

  Somewhere between Beam and the BigQuery streaming inserts API infinities and
  NaNs break if passed as is, apparently because JSON cannot represent these
  values natively.  Fortunately BigQuery appears happy to cast string values
  into floats, so we just have to intercept these values and substitute strings.

  Nones, and floats other than inf and NaN, are returned unchanged.
  """
  if f is None:
    return None
  if math.isinf(f):
    return 'inf' if f > 0 else '-inf'
  if math.isnan(f):
    return 'NaN'
  return f


def PrintCounters(pipeline_result):
  """Print pipeline counters to stdout.

  Useful for seeing metrics when running pipelines directly rather than in
  Dataflow.
  """
  try:
    metrics = pipeline_result.metrics().query()
  except ValueError:
    # Don't crash if there are no metrics, e.g. if we were run with
    # --template_location, which stages a job template but does not run the job.
    return
  for counter in metrics['counters']:
    print('Counter: ' + repr(counter))
    print('  = ' + str(counter.result))


def IsoDateToYYYYMMDD(iso_date_str):
  """Convert ISO-formatted dates to a YYYYMMDD string."""
  return iso_date_str[:4] + iso_date_str[5:7] + iso_date_str[8:10]


def _ElementToYYYYMMDD(element):
  return IsoDateToYYYYMMDD(element['timestamp'])


def _GetPartitionNameFn(table_name, element_to_yyyymmdd_fn):
  def TableWithPartitionSuffix(element):
    # Partition names are the table name with a $yyyymmdd suffix, e.g.
    # 'my_dataset.my_table$20200123'.  So extract the suffix from the ISO-format
    # timestamp value in this element.
    return table_name + '$' + element_to_yyyymmdd_fn(element)
  return TableWithPartitionSuffix


def WriteToPartitionedBigQuery(table_name,
                               schema,
                               element_to_yyyymmdd_fn=_ElementToYYYYMMDD,
                               **kwargs):
  """Return a WriteToBigQuery configured to load into a day-partitioned table.

  This is useful for idempotent writing of whole days of data.

  Instead of writing to the table, this writes to the individual partitions
  instead (effectively treating each partition as an independent table).
  Because the table is partitioned by day, this allows us to use the
  WRITE_TRUNCATE option to regenerate the specified days without deleting the
  rest of the table.  So instead of passing a table name string as the
  destination for WriteToBigQuery, we pass a function that dynamically
  calculates the partition name.

  Because we are loading data into the partition directly we must *not* set
  'timePartitioning' in additional_bq_parameters, otherwise the load job will
  fail with a kind of schema mismatch.
  """
  return beam.io.WriteToBigQuery(
      _GetPartitionNameFn(table_name, element_to_yyyymmdd_fn),
      schema=schema,
      method=beam.io.WriteToBigQuery.Method.FILE_LOADS,
      write_disposition=beam.io.BigQueryDisposition.WRITE_TRUNCATE,
      create_disposition=beam.io.BigQueryDisposition.CREATE_NEVER,
      **kwargs)
