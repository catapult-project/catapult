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

import apache_beam as beam
from apache_beam.io.gcp.bigquery import BigQueryWriteFn
from apache_beam.options.pipeline_options import GoogleCloudOptions
from apache_beam.options.pipeline_options import PipelineOptions
from apache_beam.metrics import Metrics
from apache_beam.transforms.core import FlatMap

from bq_export.split_by_timestamp import ReadTimestampRangeFromDatastore
from bq_export.export_options import BqExportOptions
from bq_export.utils import FloatHack, PrintCounters


def main():
  project = 'chromeperf'
  options = PipelineOptions()
  options.view_as(GoogleCloudOptions).project = project
  bq_export_options = options.view_as(BqExportOptions)

  p = beam.Pipeline(options=options)
  entities_read = Metrics.counter('main', 'entities_read')
  failed_entity_transforms = Metrics.counter('main', 'failed_entity_transforms')
  failed_bq_rows = Metrics.counter('main', 'failed_bq_rows')
  def CountFailed(unused_element):
    failed_bq_rows.inc()

  # CREATE TABLE `chromeperf.chromeperf_dashboard_data.rows_test`
  # (revision INT64 NOT NULL,
  #  value FLOAT64 NOT NULL,
  #  error FLOAT64,
  #  `timestamp` TIMESTAMP NOT NULL,
  #  parent_test STRING NOT NULL,
  #  properties STRING)
  # PARTITION BY DATE(`timestamp`);
  bq_row_schema = {'fields': [
      {'name': 'revision', 'type': 'INT64', 'mode': 'REQUIRED'},
      {'name': 'value', 'type': 'FLOAT', 'mode': 'REQUIRED'},
      {'name': 'error', 'type': 'FLOAT', 'mode': 'NULLABLE'},
      {'name': 'timestamp', 'type': 'TIMESTAMP', 'mode': 'REQUIRED'},
      {'name': 'parent_test', 'type': 'STRING', 'mode': 'REQUIRED'},
      {'name': 'properties', 'type': 'STRING', 'mode': 'NULLABLE'},
  ]}
  def RowEntityToRowDict(entity):
    entities_read.inc()
    try:
      d = {
          'revision': entity.key.id,
          'value': FloatHack(entity['value']),
          'error': FloatHack(entity.get('error')),
          'timestamp': entity['timestamp'].isoformat(),
          'parent_test': entity.key.parent.name,
      }
      # Add the expando properties as a JSON-encoded dict.
      properties = {}
      for key, value in entity.items():
        if key in d:
          # skip properties with dedicated columns.
          continue
        if isinstance(value, float):
          value = FloatHack(value)
        properties[key] = value
      d['properties'] = json.dumps(properties) if properties else None
      return [d]
    except KeyError:
      logging.getLogger().exception('Failed to convert Row')
      failed_entity_transforms.inc()
      return []

  print("Time range: %s -> %s" % (
      bq_export_options.StartTime(), bq_export_options.EndTime()))
  row_query_params = dict(project=project, kind='Row')
  row_entities = (
      p
      | 'ReadFromDatastore(Row)' >> ReadTimestampRangeFromDatastore(
          row_query_params,
          min_timestamp=bq_export_options.StartTime(),
          max_timestamp=bq_export_options.EndTime(),
          step=datetime.timedelta(minutes=10)))

  row_dicts = (
      row_entities | 'ConvertEntityToRow(Row)' >> FlatMap(RowEntityToRowDict))

  additional_bq_parameters = {
      'timePartitioning': {'type': 'DAY', 'field': 'timestamp'},
  }

  # TODO(abennetts): clear any day partitions that we are about to overwrite.
  bq_rows = (
      row_dicts | 'WriteToBigQuery(rows)' >> beam.io.WriteToBigQuery(
          '{}:chromeperf_dashboard_data.rows_test'.format(project),
          schema=bq_row_schema,
          method=beam.io.WriteToBigQuery.Method.STREAMING_INSERTS,
          write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
          create_disposition=beam.io.BigQueryDisposition.CREATE_NEVER,
          additional_bq_parameters=additional_bq_parameters,
      ))
  failed_row_inserts = bq_rows[BigQueryWriteFn.FAILED_ROWS]
  _ = failed_row_inserts | 'CountFailed(Row)' >> beam.Map(CountFailed)

  result = p.run()
  result.wait_until_finish()
  PrintCounters(result)
