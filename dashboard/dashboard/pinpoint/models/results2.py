# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import collections
import cloudstorage
import logging
import os
import uuid

from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from apiclient.discovery import build
from dashboard.pinpoint.models import job_state
from dashboard.pinpoint.models.quest import read_value
from dashboard.pinpoint.models.quest import run_test
from dashboard.services import swarming
from oauth2client import client
from tracing_build import render_histograms_viewer
from tracing.value import gtest_json_converter
from tracing.value.diagnostics import generic_set
from tracing.value.diagnostics import reserved_infos

# Maps metric name -> position in the measures tree of the BQ export
_METRIC_MAP = {
    # CWV
    "largestContentfulPaint": ("core_web_vitals", "largestContentfulPaint"),
    "timeToFirstContentfulPaint":
        ("core_web_vitals", "timeToFirstContentfulPaint"),
    "overallCumulativeLayoutShift":
        ("core_web_vitals", "overallCumulativeLayoutShift"),
    "totalBlockingTime": ("core_web_vitals", "totalBlockingTime"),

    # Speedometer2
    "Angular2-TypeScript-TodoMVC":
        ("speedometer2", "Angular2_TypeScript_TodoMVC"),
    "AngularJS-TodoMVC": ("speedometer2", "AngularJS_TodoMVC"),
    "BackboneJS-TodoMVC": ("speedometer2", "BackboneJS_TodoMVC"),
    "Elm-TodoMVC": ("speedometer2", "Elm_TodoMVC"),
    "EmberJS-Debug-TodoMVC": ("speedometer2", "EmberJS_Debug_TodoMVC"),
    "EmberJS-TodoMVC": ("speedometer2", "EmberJS_TodoMVC"),
    "Flight-TodoMVC": ("speedometer2", "Flight_TodoMVC"),
    "Inferno-TodoMVC": ("speedometer2", "Inferno_TodoMVC"),
    "jQuery-TodoMVC": ("speedometer2", "jQuery_TodoMVC"),
    "Preact-TodoMVC": ("speedometer2", "Preact_TodoMVC"),
    "React-Redux-TodoMVC": ("speedometer2", "React_Redux_TodoMVC"),
    "React-TodoMVC": ("speedometer2", "React_TodoMVC"),
    "Vanilla-ES2015-Babel-Webpack-TodoMVC":
        ("speedometer2", "Vanilla_ES2015_Babel_Webpack_TodoMVC"),
    "Vanilla-ES2015-TodoMVC": ("speedometer2", "Vanilla_ES2015_TodoMVC"),
    "VanillaJS-TodoMVC": ("speedometer2", "VanillaJS_TodoMVC"),
    "VueJS-TodoMVC": ("speedometer2", "VueJS_TodoMVC")
}

_PROJECT_ID = 'chromeperf'

_DATASET_CHROME_HEALTH = 'pinpoint_export_test'
_TABLE_CHROME_HEALTH = 'pinpoint_results'

_DATASET_GENERAL = 'pinpoint_export'
_TABLE_GENERAL = 'results'


class Results2Error(Exception):

  pass


class CachedResults2(ndb.Model):
  """Stores data on when a results2 was generated."""

  updated = ndb.DateTimeProperty(required=True, auto_now_add=True)
  job_id = ndb.StringProperty()


class _GcsFileStream(object):
  """Wraps a gcs file providing a FileStream like api."""

  # pylint: disable=invalid-name

  def __init__(self, *args, **kwargs):
    self._gcs_file = cloudstorage.open(*args, **kwargs)

  def seek(self, _):
    pass

  def truncate(self):
    pass

  def write(self, data):
    self._gcs_file.write(data)

  def close(self):
    self._gcs_file.close()


def _GetCloudStorageName(job_id):
  return '/results2-public/%s.html' % job_id


def GetCachedResults2(job):
  filename = _GetCloudStorageName(job.job_id)
  results = cloudstorage.listbucket(filename)

  for _ in results:
    return 'https://storage.cloud.google.com' + filename

  return None


def ScheduleResults2Generation(job):
  logging.debug('Job [%s]: ScheduleResults2Generation', job.job_id)
  try:
    # Don't want several tasks creating results2, so create task with specific
    # name to deduplicate.
    task_name = 'results2-public-%s' % job.job_id
    taskqueue.add(
        queue_name='job-queue',
        url='/api/generate-results2/' + job.job_id,
        name=task_name)
  except taskqueue.TombstonedTaskError:
    return False
  except taskqueue.TaskAlreadyExistsError:
    pass
  return True


def GenerateResults2(job):
  """ Generates a results2.html and also adds results to BigQuery. """
  logging.debug('Job [%s]: GenerateResults2', job.job_id)

  vulcanized_html = _ReadVulcanizedHistogramsViewer()

  CachedResults2(job_id=job.job_id).put()

  filename = _GetCloudStorageName(job.job_id)
  gcs_file = _GcsFileStream(
      filename,
      'w',
      content_type='text/html',
      retry_params=cloudstorage.RetryParams(backoff_factor=1.1))

  render_histograms_viewer.RenderHistogramsViewer(
      [h.histogram for h in _FetchHistograms(job)],
      gcs_file,
      reset_results=True,
      vulcanized_html=vulcanized_html)

  gcs_file.close()
  logging.debug('Generated %s; see https://storage.cloud.google.com%s',
                filename, filename)

  # Only save A/B tests to the Chrome Health BigQuery
  if job.comparison_mode != job_state.FUNCTIONAL and job.comparison_mode != job_state.PERFORMANCE:
    try:
      _SaveJobToChromeHealthBigQuery(job)
    except Exception as e:  # pylint: disable=broad-except
      logging.error(e)

  # Export every job to the General BigQuery
  try:
    _SaveJobToGeneralBigQuery(job)
  except Exception as e:  # pylint: disable=broad-except
    logging.error(e)


def _ReadVulcanizedHistogramsViewer():
  viewer_path = os.path.join(
      os.path.dirname(__file__), '..', '..', '..',
      'vulcanized_histograms_viewer', 'vulcanized_histograms_viewer.html')
  with open(viewer_path, 'r') as f:
    return f.read()

HistogramMetadata = collections.namedtuple(
    'HistogramMetadata', ['attempt_number', "change", "swarming_result"])
HistogramData = collections.namedtuple('HistogramMetadata',
                                       ["metadata", "histogram"])


def _FetchHistograms(job):
  for change in _ChangeList(job):
    for attempt_number, attempt in enumerate(job.state._attempts[change]):
      swarming_result = None
      for execution in attempt.executions:
        # Attempt to extract taskID if this is a run_test._RunTestExecution
        if isinstance(execution, run_test._RunTestExecution):
          # Query Swarming
          try:
            swarming_task = swarming.Swarming(execution._swarming_server).Task(
                execution._task_id)
            swarming_result = swarming_task.Result()
          except Exception as e:  # pylint: disable=broad-except
            logging.error("_FetchHistograms swarming query failed: " + str(e))
          continue

        # Attempt to extract Histograms if this is a read_value.*
        mode = None
        if isinstance(execution, read_value._ReadHistogramsJsonValueExecution):
          mode = 'histograms'
        elif isinstance(execution, read_value._ReadGraphJsonValueExecution):
          mode = 'graphjson'
        elif isinstance(execution, read_value.ReadValueExecution):
          mode = execution.mode or 'histograms'

        if mode is None:
          continue

        histogram_sets = None
        if mode == 'graphjson':
          histograms = gtest_json_converter.ConvertGtestJson(
              _JsonFromExecution(execution))
          histograms.AddSharedDiagnosticToAllHistograms(
              reserved_infos.LABELS.name, generic_set.GenericSet([str(change)]))
          histogram_sets = histograms.AsDicts()
        else:
          histogram_sets = _JsonFromExecution(execution)

        logging.debug('Found %s histograms for %s', len(histogram_sets), change)

        metadata = HistogramMetadata(attempt_number, change, swarming_result)
        for histogram in histogram_sets:
          yield HistogramData(metadata, histogram)

        # Force deletion of histogram_set objects which can be O(100MB).
        del histogram_sets


def _ChangeList(job):
  # If there are differences, only include Changes with differences.
  changes = set()

  for change_a, change_b in job.state.Differences():
    changes.add(change_a)
    changes.add(change_b)

  if changes:
    return list(changes)

  return job.state._changes


def _JsonFromExecution(execution):
  if hasattr(execution, '_cas_root_ref') and execution._cas_root_ref:
    return read_value.RetrieveOutputJsonFromCAS(
        execution._cas_root_ref,
        execution._results_path,
    )

  if hasattr(execution, '_results_filename'):
    results_filename = execution._results_filename
  else:
    results_filename = 'chartjson-output.json'

  if hasattr(execution, '_isolate_server'):
    isolate_server = execution._isolate_server
  else:
    isolate_server = 'https://isolateserver.appspot.com'
  isolate_hash = execution._isolate_hash
  return read_value.RetrieveOutputJson(
      isolate_server,
      isolate_hash,
      results_filename,
  )


def _SaveJobToGeneralBigQuery(job):
  rows = []
  for h in _FetchHistograms(job):
    if "sampleValues" not in h.histogram:
      continue
    row = _PopulateMetadata(job, h)
    row["metric"] = h.histogram["name"]
    row["values"] = h.histogram["sampleValues"]
    rows.append(row)
  if len(rows):
    _InsertBQRows(_PROJECT_ID, _DATASET_GENERAL, _TABLE_GENERAL, rows)

RowKey = collections.namedtuple('RowKey', ['change', 'iteration'])
def _SaveJobToChromeHealthBigQuery(job):
  rows = {}  # Key is a RowKey
  for h in _FetchHistograms(job):
    if "sampleValues" not in h.histogram:
      continue
    if len(h.histogram["sampleValues"]) != 1:
      # We don't support analysis of metrics with more than one sample.
      continue
    rk = RowKey(h.metadata.change, h.metadata.attempt_number)
    if rk not in rows:
      rows[rk] = _PopulateMetadata(job, h)
      rows[rk]["measures"] = _GetEmptyMeasures()
    rows[rk] = _PopulateMetric(rows[rk], h.histogram["name"],
                               h.histogram["sampleValues"][0])
  empty_measures = _GetEmptyMeasures()
  rows_with_measures = [
      r for r in rows.values() if r["measures"] != empty_measures
  ]
  if len(rows_with_measures):
    _InsertBQRows(_PROJECT_ID, _DATASET_CHROME_HEALTH, _TABLE_CHROME_HEALTH,
                  rows_with_measures)


def _GetEmptyMeasures():
  measures = {}
  measures["core_web_vitals"] = {}
  measures["speedometer2"] = {}
  return measures


def _PopulateMetric(data, name, value):
  if name in _METRIC_MAP:
    loc = _METRIC_MAP[name]
    data["measures"][loc[0]][loc[1]] = float(value)

  return data


def _PopulateMetadata(job, h):
  md = {}
  md["job_start_time"] = _ConvertDatetimeToBQ(job.started_time)
  md["batch_id"] = job.batch_id
  md["run_id"] = job.job_id
  md["dims"] = {}
  md["dims"]["device"] = {}
  md["dims"]["device"]["cfg"] = job.configuration
  if h.metadata.swarming_result and "bot_dimensions" in h.metadata.swarming_result:
    # bot_dimensions is a list of dicts with "key" and "value" entries.
    for kv in h.metadata.swarming_result["bot_dimensions"]:
      if kv["key"] == "device_os":
        md["dims"]["device"]["os"] = kv["value"]
      # device_os should take precedence over os
      # if both are present, os is more generic.
      if kv["key"] == "os" and "os" not in md["dims"]["device"]:
        md["dims"]["device"]["os"] = kv["value"]
      if kv["key"] == "id" and len(kv["value"]) > 0:
        md["dims"]["device"]["swarming_bot_id"] = kv["value"][0]
  md["dims"]["test_info"] = {}
  md["dims"]["test_info"]["benchmark"] = job.benchmark_arguments.benchmark
  md["dims"]["test_info"]["story"] = job.benchmark_arguments.story
  # TODO: flags
  md["dims"]["checkout"] = {}
  # TODO: gitiles_host
  md["dims"]["checkout"]["repo"] = h.metadata.change.commits[0].repository
  md["dims"]["checkout"]["git_hash"] = h.metadata.change.commits[0].git_hash
  commit_dict = h.metadata.change.commits[0].AsDict()
  if "commit_position" in commit_dict:
    md["dims"]["checkout"]["commit_created"] = _ConvertIsotimeToBQ(
        commit_dict["created"])
    md["dims"]["checkout"]["branch"] = commit_dict["commit_branch"]
    md["dims"]["checkout"]["commit_position"] = commit_dict["commit_position"]
  if h.metadata.change.patch is not None:
    patch_params = h.metadata.change.patch.BuildParameters()
    md["dims"]["checkout"]["patch_gerrit_change"] = patch_params["patch_issue"]
    md["dims"]["checkout"]["patch_gerrit_revision"] = patch_params["patch_set"]
  md["dims"]["pairing"] = {}
  md["dims"]["pairing"]["variant"] = h.metadata.change.variant
  md["dims"]["pairing"]["replica"] = h.metadata.attempt_number
  # TODO: order (not implemented yet)

  return md

def _ConvertIsotimeToBQ(it):
  return it.replace('T', ' ') + ".000000"

def _ConvertDatetimeToBQ(dt):
  return dt.strftime('%Y-%m-%d %H:%M:%S.%f')


def _InsertBQRows(project_id, dataset_id, table_id, rows, num_retries=5):
  service = _BQService()
  rows = [{'insertId': str(uuid.uuid4()), 'json': row} for row in rows]
  insert_data = {'rows': rows}
  logging.info("Saving to BQ: " + str(insert_data))
  response = service.tabledata().insertAll(
      projectId=project_id,
      datasetId=dataset_id,
      tableId=table_id,
      body=insert_data).execute(num_retries=num_retries)

  if 'insertErrors' in response:
    logging.error("Insert failed: " + str(response))


def _BQService():
  """Returns an initialized and authorized BigQuery client."""
  # pylint: disable=no-member
  credentials = client.GoogleCredentials.get_application_default()
  if credentials.create_scoped_required():
    credentials = credentials.create_scoped(
        'https://www.googleapis.com/auth/bigquery')
  return build('bigquery', 'v2', credentials=credentials)
