# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Export CloudWorkflow data to BigQuery with Beam & Cloud Dataflow."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import json
import logging
import six

import apache_beam as beam
from apache_beam.options.pipeline_options import DebugOptions
from apache_beam.options.pipeline_options import GoogleCloudOptions
from apache_beam.options.pipeline_options import PipelineOptions
from apache_beam.metrics import Metrics

from bq_export.split_by_timestamp import ReadTimestampRangeFromDatastore
from bq_export.export_options import BqExportOptions
from bq_export.utils import (PrintCounters, WriteToPartitionedBigQuery,
                             UnconvertibleEntityError, IsoDateToYYYYMMDD)


def _ConvertOptionalDateTime(dt):
  """Converts a datetime object to an ISO 8601 string, or returns None."""
  if dt is None:
    return None
  return dt.isoformat()


def _WorkflowToYYYYMMDD(row_dict):
  """
  Extracts the YYYYMMDD string from the 'started' timestamp for partitioning.
  If 'started' is missing, it returns None, placing the row in the __NULL__ partition.
  """
  started_time = row_dict.get('started')
  if not started_time:
    return None
  return IsoDateToYYYYMMDD(started_time)


def _safely_load_json(data):
  """Safely loads a JSON object that might be a dict, bytes, string, or None."""
  if isinstance(data, dict):
    return data
  if isinstance(data, (bytes, str)):
    try:
      return json.loads(data)
    except (json.JSONDecodeError, TypeError):
      logging.warning("Could not decode JSON data: %s", data)
      return {}
  return {}


def WorkflowEntityToRowDict(entity):
  """
  Converts a Datastore entity for a CloudWorkflow into a dictionary for BigQuery.

  This function flattens the nested JSON properties (`commit_dict`, `anomaly`,
  `statistic`) into top-level fields in the resulting dictionary. It safely
  accesses all properties to avoid errors if a property is missing.
  """
  try:
    # Safely get nested JSON properties. If a property is missing,
    # default to an empty dictionary to prevent subsequent errors.
    commit_dict = _safely_load_json(entity.get('commit_dict'))
    anomaly_dict = _safely_load_json(entity.get('anomaly'))
    statistic_dict = _safely_load_json(entity.get('statistic'))

    # Create the base dictionary with all the fields for the BigQuery row.
    d = {
        'execution_name': entity.get('execution_name'),
        'execution_status': entity.get('execution_status'),
        'kind': entity.get('kind'),
        'values_a': entity.get('values_a', []),
        'values_b': entity.get('values_b', []),
        'decision': entity.get('decision'),
        'job_id': entity.get('job_id'),
        'started': _ConvertOptionalDateTime(entity.get('started')),
        'finished': _ConvertOptionalDateTime(entity.get('finished')),

        # Flattened fields from commit_dict
        'commit_repository': commit_dict.get('repository'),
        'commit_git_hash': commit_dict.get('git_hash'),
        'commit_cl_number': commit_dict.get('cl_number'),

        # Flattened fields from anomaly
        'anomaly_benchmark': anomaly_dict.get('benchmark'),
        'anomaly_bot_name': anomaly_dict.get('bot_name'),
        'anomaly_end_git_hash': anomaly_dict.get('end_git_hash'),
        'anomaly_improvement_dir': anomaly_dict.get('improvement_dir'),
        'anomaly_measurement': anomaly_dict.get('measurement'),
        'anomaly_project': anomaly_dict.get('project'),
        'anomaly_start_git_hash': anomaly_dict.get('start_git_hash'),
        'anomaly_story': anomaly_dict.get('story'),
        'anomaly_target': anomaly_dict.get('target'),

        # Flattened fields from statistic
        'statistic_control_median': statistic_dict.get('control_median'),
        'statistic_lower': statistic_dict.get('lower'),
        'statistic_p_value': statistic_dict.get('p_value'),
        'statistic_treatment_median': statistic_dict.get('treatment_median'),
        'statistic_upper': statistic_dict.get('upper'),
    }
  except KeyError as e:
    # This will catch cases where the required 'started' field is missing.
    six.raise_from(
        UnconvertibleEntityError('Missing required property: ' + str(e)), e)
  return d


def main():
  # Set your Google Cloud project ID here.
  project = 'chromeperf'
  options = PipelineOptions()
  options.view_as(DebugOptions).add_experiment('use_beam_bq_sink')
  options.view_as(GoogleCloudOptions).project = project
  bq_export_options = options.view_as(BqExportOptions)

  p = beam.Pipeline(options=options)
  entities_read = Metrics.counter('main', 'entities_read')
  failed_entity_transforms = Metrics.counter('main', 'failed_entity_transforms')

  # Read 'CloudWorkflow' entities from Datastore, filtering by the 'started' timestamp.
  workflow_entities = (
      p
      | 'ReadFromDatastore(CloudWorkflow)' >> ReadTimestampRangeFromDatastore(
          {
              'project': project,
              'kind': 'CloudWorkflow'
          },
          time_range_provider=bq_export_options.GetTimeRangeProvider(),
          timestamp_property='started'))

  def ConvertEntity(entity):
    """Wrapper function to handle metrics and errors during conversion."""
    entities_read.inc()
    try:
      row_dict = WorkflowEntityToRowDict(entity)
    except UnconvertibleEntityError:
      logging.getLogger().exception('Failed to convert CloudWorkflow entity')
      failed_entity_transforms.inc()
      return []
    return [row_dict]

  workflow_dicts = (
      workflow_entities
      | 'ConvertEntityToRow(CloudWorkflow)' >> beam.FlatMap(ConvertEntity))

  # This is the BigQuery table schema in SQL format for documentation.
  _ = """
  CREATE TABLE `chromeperf.chromeperf_dashboard_data.culprit_workflows`
  (
    execution_name STRING,
    execution_status STRING,
    kind STRING,
    commit_repository STRING,
    commit_git_hash STRING,
    commit_cl_number STRING,
    values_a FLOAT64,
    values_b FLOAT64,
    decision BOOLEAN,
    job_id STRING,
    anomaly_benchmark STRING,
    anomaly_bot_name STRING,
    anomaly_end_git_hash STRING,
    anomaly_improvement_dir STRING,
    anomaly_measurement STRING,
    anomaly_project STRING,
    anomaly_start_git_hash STRING,
    anomaly_story STRING,
    anomaly_target STRING,
    statistic_control_median FLOAT64,
    statistic_lower FLOAT64,
    statistic_p_value FLOAT64,
    statistic_treatment_median FLOAT64,
    statistic_upper FLOAT64,
    started TIMESTAMP NOT NULL,
    finished TIMESTAMP
  )
  PARTITION BY DATE(started);
  """

  # This is the BigQuery schema in the format required by the Beam API.
  bq_workflow_schema = {
      'fields': [
          {
              'name': 'execution_name',
              'type': 'STRING',
              'mode': 'NULLABLE'
          },
          {
              'name': 'execution_status',
              'type': 'STRING',
              'mode': 'NULLABLE'
          },
          {
              'name': 'kind',
              'type': 'STRING',
              'mode': 'NULLABLE'
          },
          {
              'name': 'commit_repository',
              'type': 'STRING',
              'mode': 'NULLABLE'
          },
          {
              'name': 'commit_git_hash',
              'type': 'STRING',
              'mode': 'NULLABLE'
          },
          {
              'name': 'commit_cl_number',
              'type': 'STRING',
              'mode': 'NULLABLE'
          },
          {
              'name': 'values_a',
              'type': 'FLOAT',
              'mode': 'REPEATED'
          },
          {
              'name': 'values_b',
              'type': 'FLOAT',
              'mode': 'REPEATED'
          },
          {
              'name': 'decision',
              'type': 'BOOLEAN',
              'mode': 'NULLABLE'
          },
          {
              'name': 'job_id',
              'type': 'STRING',
              'mode': 'NULLABLE'
          },
          {
              'name': 'anomaly_benchmark',
              'type': 'STRING',
              'mode': 'NULLABLE'
          },
          {
              'name': 'anomaly_bot_name',
              'type': 'STRING',
              'mode': 'NULLABLE'
          },
          {
              'name': 'anomaly_end_git_hash',
              'type': 'STRING',
              'mode': 'NULLABLE'
          },
          {
              'name': 'anomaly_improvement_dir',
              'type': 'STRING',
              'mode': 'NULLABLE'
          },
          {
              'name': 'anomaly_measurement',
              'type': 'STRING',
              'mode': 'NULLABLE'
          },
          {
              'name': 'anomaly_project',
              'type': 'STRING',
              'mode': 'NULLABLE'
          },
          {
              'name': 'anomaly_start_git_hash',
              'type': 'STRING',
              'mode': 'NULLABLE'
          },
          {
              'name': 'anomaly_story',
              'type': 'STRING',
              'mode': 'NULLABLE'
          },
          {
              'name': 'anomaly_target',
              'type': 'STRING',
              'mode': 'NULLABLE'
          },
          {
              'name': 'statistic_control_median',
              'type': 'FLOAT',
              'mode': 'NULLABLE'
          },
          {
              'name': 'statistic_lower',
              'type': 'FLOAT',
              'mode': 'NULLABLE'
          },
          {
              'name': 'statistic_p_value',
              'type': 'FLOAT',
              'mode': 'NULLABLE'
          },
          {
              'name': 'statistic_treatment_median',
              'type': 'FLOAT',
              'mode': 'NULLABLE'
          },
          {
              'name': 'statistic_upper',
              'type': 'FLOAT',
              'mode': 'NULLABLE'
          },
          {
              'name': 'started',
              'type': 'TIMESTAMP',
              'mode': 'NULLABLE'
          },
          {
              'name': 'finished',
              'type': 'TIMESTAMP',
              'mode': 'NULLABLE'
          },
      ]
  }

  # This function dynamically creates the table name at runtime.
  def TableNameFn(unused_element):
    return '{}:{}.culprit_workflows{}'.format(project,
                                              bq_export_options.dataset.get(),
                                              bq_export_options.table_suffix)

  _ = workflow_dicts | 'WriteToBigQuery' >> WriteToPartitionedBigQuery(
      TableNameFn,
      bq_workflow_schema,
      element_to_yyyymmdd_fn=_WorkflowToYYYYMMDD)

  result = p.run()
  result.wait_until_finish()
  PrintCounters(result)


if __name__ == '__main__':
  main()
