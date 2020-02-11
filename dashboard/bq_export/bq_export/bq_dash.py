# Copyright (c) 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Export chromeperf dashboard data to BigQuery with Beam & Cloud Dataflow."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import apache_beam as beam
from apache_beam.io.gcp.bigquery import BigQueryWriteFn
from apache_beam.options.pipeline_options import GoogleCloudOptions
from apache_beam.options.pipeline_options import PipelineOptions
from apache_beam.metrics import Metrics

from bq_export.split_by_timestamp import ReadTimestampRangeFromDatastore
from bq_export.export_options import BqExportOptions
from bq_export.utils import TestPath, FloatHack, PrintCounters


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

  # Read 'Anomaly' entities from datastore.
  entities = (
      p
      | 'ReadFromDatastore(Anomaly)' >> ReadTimestampRangeFromDatastore(
          {'project': project, 'kind': 'Anomaly'},
          min_timestamp=bq_export_options.StartTime(),
          max_timestamp=bq_export_options.EndTime()))

  def AnomalyEntityToRowDict(entity):
    entities_read.inc()
    try:
      d = {
          'id': entity.key.id,
          # TODO: 'sheriff'
          # 'subscriptions' omitted; subscription_names is sufficient
          'subscription_names': entity.get('subscription_names', []),
          'test': TestPath(entity['test']),
          'start_revision': entity['start_revision'],
          'end_revision': entity['end_revision'],
          'display_start': entity.get('display_start'),
          'display_end': entity.get('display_end'),
          # TODO: 'ownership'
          'statistic': entity['statistic'],
          'bug_id': entity['bug_id'],
          'internal_only': entity['internal_only'],
          'timestamp': entity['timestamp'].isoformat(),
          'segment_size_before': entity.get('segment_size_before'),
          'segment_size_after': entity.get('segment_size_after'),
          'median_before_anomaly': entity.get('median_before_anomaly'),
          'median_after_anomaly': entity.get('median_after_anomaly'),
          'std_dev_before_anomaly': entity.get('std_dev_before_anomaly'),
          'window_end_revision': entity.get('window_end_revision'),
          't_statistic': FloatHack(entity.get('t_statistic')),
          'degrees_of_freedom': entity.get('degrees_of_freedom'),
          'p_value': entity.get('p_value'),
          'is_improvement': entity.get('is_improvement', False),
          'recovered': entity.get('recovered', False),
          # TODO: 'ref_test'
          'units': entity.get('units'),
          # TODO: 'recipe_bisects'
          'pinpoint_bisects': entity.get('pinpoint_bisects', []),
      }
      return [d]
    except KeyError:
      failed_entity_transforms.inc()
      return []
  anomaly_dicts = (
      entities
      | 'ConvertEntityToRow(Anomaly)' >> beam.FlatMap(AnomalyEntityToRowDict))

  bq_anomaly_schema = {'fields': [
      {'name': 'id', 'type': 'INT64', 'mode': 'REQUIRED'},
      {'name': 'subscription_names', 'type': 'STRING', 'mode': 'REPEATED'},
      {'name': 'test', 'type': 'STRING', 'mode': 'REQUIRED'},
      {'name': 'start_revision', 'type': 'INT64', 'mode': 'REQUIRED'},
      {'name': 'end_revision', 'type': 'INT64', 'mode': 'REQUIRED'},
      {'name': 'display_start', 'type': 'INT64', 'mode': 'NULLABLE'},
      {'name': 'display_end', 'type': 'INT64', 'mode': 'NULLABLE'},
      {'name': 'statistic', 'type': 'STRING', 'mode': 'REQUIRED'},
      {'name': 'bug_id', 'type': 'INT64', 'mode': 'NULLABLE'},
      {'name': 'internal_only', 'type': 'BOOLEAN', 'mode': 'REQUIRED'},
      {'name': 'timestamp', 'type': 'TIMESTAMP', 'mode': 'REQUIRED'},
      {'name': 'segment_size_before', 'type': 'INT64', 'mode': 'NULLABLE'},
      {'name': 'segment_size_after', 'type': 'INT64', 'mode': 'NULLABLE'},
      {'name': 'median_before_anomaly', 'type': 'FLOAT', 'mode': 'NULLABLE'},
      {'name': 'median_after_anomaly', 'type': 'FLOAT', 'mode': 'NULLABLE'},
      {'name': 'std_dev_before_anomaly', 'type': 'FLOAT', 'mode': 'NULLABLE'},
      {'name': 'window_end_revision', 'type': 'INT64', 'mode': 'NULLABLE'},
      {'name': 't_statistic', 'type': 'FLOAT', 'mode': 'NULLABLE'},
      {'name': 'degrees_of_freedom', 'type': 'FLOAT', 'mode': 'NULLABLE'},
      {'name': 'p_value', 'type': 'FLOAT', 'mode': 'NULLABLE'},
      {'name': 'is_improvement', 'type': 'BOOLEAN', 'mode': 'REQUIRED'},
      {'name': 'recovered', 'type': 'BOOLEAN', 'mode': 'REQUIRED'},
      {'name': 'units', 'type': 'STRING', 'mode': 'NULLABLE'},
      {'name': 'pinpoint_bisects', 'type': 'STRING', 'mode': 'REPEATED'},
  ]}

  bq_anomalies = (
      anomaly_dicts | 'WriteToBigQuery(anomalies)' >> beam.io.WriteToBigQuery(
          '{}:chromeperf_dashboard_data.anomalies_test'.format(project),
          schema=bq_anomaly_schema,
          method=beam.io.WriteToBigQuery.Method.STREAMING_INSERTS,
          write_disposition=beam.io.BigQueryDisposition.WRITE_TRUNCATE,
          create_disposition=beam.io.BigQueryDisposition.CREATE_NEVER))

  failed_anomaly_inserts = bq_anomalies[BigQueryWriteFn.FAILED_ROWS]
  _ = failed_anomaly_inserts | 'CountFailed(Anomaly)' >> beam.Map(CountFailed)

  result = p.run()
  result.wait_until_finish()
  PrintCounters(result)

