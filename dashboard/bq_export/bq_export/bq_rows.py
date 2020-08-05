# Copyright (c) 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Export chromeperf Row data to BigQuery with Beam & Cloud Dataflow."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import datetime
import json
import logging
import re

import apache_beam as beam
from apache_beam.options.pipeline_options import DebugOptions
from apache_beam.options.pipeline_options import GoogleCloudOptions
from apache_beam.options.pipeline_options import PipelineOptions
from apache_beam.metrics import Metrics
from apache_beam.transforms.core import FlatMap

from bq_export.split_by_timestamp import ReadTimestampRangeFromDatastore
from bq_export.export_options import BqExportOptions
from bq_export.utils import (FloatHack, PrintCounters,
                             WriteToPartitionedBigQuery)

# BigQuery table names may only have letters, numbers, and underscore.
_INVALID_BQ_TABLE_NAME_CHARS_RE = re.compile('[^a-zA-Z0-9_]')


def main():
  project = 'chromeperf'
  options = PipelineOptions()
  options.view_as(DebugOptions).add_experiment('use_beam_bq_sink')
  options.view_as(GoogleCloudOptions).project = project
  bq_export_options = options.view_as(BqExportOptions)

  p = beam.Pipeline(options=options)
  entities_read = Metrics.counter('main', 'entities_read')
  failed_entity_transforms = Metrics.counter('main', 'failed_entity_transforms')

  """
  CREATE TABLE `chromeperf.chromeperf_dashboard_rows.<MASTER>`
  (revision INT64 NOT NULL,
   value FLOAT64 NOT NULL,
   std_error FLOAT64,
   `timestamp` TIMESTAMP NOT NULL,
   master STRING NOT NULL,
   bot STRING NOT NULL,
   measurement STRING,
   test STRING NOT NULL,
   properties STRING)
  PARTITION BY DATE(`timestamp`)
  CLUSTER BY master, bot, measurement;
  """  # pylint: disable=pointless-string-statement
  bq_row_schema = {
      'fields': [
          {
              'name': 'revision',
              'type': 'INT64',
              'mode': 'REQUIRED'
          },
          {
              'name': 'value',
              'type': 'FLOAT',
              'mode': 'REQUIRED'
          },
          {
              'name': 'std_error',
              'type': 'FLOAT',
              'mode': 'NULLABLE'
          },
          {
              'name': 'timestamp',
              'type': 'TIMESTAMP',
              'mode': 'REQUIRED'
          },
          {
              'name': 'master',
              'type': 'STRING',
              'mode': 'REQUIRED'
          },
          {
              'name': 'bot',
              'type': 'STRING',
              'mode': 'REQUIRED'
          },
          {
              'name': 'measurement',
              'type': 'STRING',
              'mode': 'NULLABLE'
          },
          {
              'name': 'test',
              'type': 'STRING',
              'mode': 'REQUIRED'
          },
          {
              'name': 'properties',
              'type': 'STRING',
              'mode': 'NULLABLE'
          },
      ]
  }

  def RowEntityToRowDict(entity):
    entities_read.inc()
    try:
      d = {
          'revision': entity.key.id,
          'value': FloatHack(entity['value']),
          'std_error': FloatHack(entity.get('error')),
          'timestamp': entity['timestamp'].isoformat(),
          'test': entity.key.parent.name,
      }
      # Add the expando properties as a JSON-encoded dict.
      properties = {}
      for key, value in entity.items():
        if key in d or key in ['parent_test', 'error']:
          # skip properties with dedicated columns.
          continue
        if isinstance(value, float):
          value = FloatHack(value)
        properties[key] = value
      d['properties'] = json.dumps(properties) if properties else None
      # Add columns derived from test: master, bot.
      test_path_parts = d['test'].split('/', 2)
      if len(test_path_parts) >= 3:
        d['master'] = test_path_parts[0]
        d['bot'] = test_path_parts[1]
        d['measurement'] = '/'.join(test_path_parts[2:])
      return [d]
    except KeyError:
      logging.getLogger().exception('Failed to convert Row')
      failed_entity_transforms.inc()
      return []

  row_query_params = dict(project=project, kind='Row')
  row_entities = (
      p
      | 'ReadFromDatastore(Row)' >> ReadTimestampRangeFromDatastore(
          row_query_params,
          time_range_provider=bq_export_options.GetTimeRangeProvider(),
          step=datetime.timedelta(minutes=5)))

  row_dicts = (
      row_entities | 'ConvertEntityToRow(Row)' >> FlatMap(RowEntityToRowDict))

  def TableNameFn(element):
    """Write each element to a table based on the table name."""
    master = _INVALID_BQ_TABLE_NAME_CHARS_RE.sub('_', element['master'])
    return '{project}:{dataset}.{master}{suffix}'.format(
        project=project,
        dataset=bq_export_options.dataset.get(),
        master=master,
        suffix=bq_export_options.table_suffix)

  _ = row_dicts | 'WriteToBigQuery(rows)' >> WriteToPartitionedBigQuery(
      TableNameFn, bq_row_schema)

  result = p.run()
  result.wait_until_finish()
  PrintCounters(result)
