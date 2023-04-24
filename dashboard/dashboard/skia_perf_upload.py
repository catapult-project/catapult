# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import cloudstorage
import datetime
import json
import logging
import time

from google.appengine.ext import ndb

from dashboard.common import cloud_metric
from dashboard.common import datastore_hooks
from dashboard.common import utils
from dashboard.models import anomaly

from flask import request, make_response

_TASK_QUEUE_NAME = 'skia-perf-upload-queue'

PUBLIC_BUCKET_NAME = 'chrome-perf-public'
INTERNAL_BUCKET_NAME = 'chrome-perf-non-public'


@cloud_metric.APIMetric("chromeperf", "/skia_perf_upload")
def SkiaPerfUploadPost():
  """
  Upload a list of ChromePerf Rows to Skia Perf.

  Args:
    Rows: A list of urlsafe encoded Rows.
  """
  datastore_hooks.SetPrivilegedRequest()
  try:
    row_ids = json.loads(request.get_data())['rows']
  except ValueError:
    row_ids = request.form.get('rows')
  rows = [ndb.Key(urlsafe=row_id).get() for row_id in row_ids]
  for row in rows:
    test_path = utils.TestPath(row.parent_test)
    try:
      if hasattr(row, 'r_commit_pos'):
        UploadRow(row)
        cloud_metric.PublishSkiaUploadResult(test_path, '', 'Completed')
      else:
        cloud_metric.PublishSkiaUploadResult(test_path,
                                             'Row has no r_commit_pos.',
                                             'Failed')
    except Exception as e:  # pylint: disable=broad-except
      logging.info('Failed to upload Row with Test: %s. Error: %s.', test_path,
                   str(e))
      cloud_metric.PublishSkiaUploadResult(test_path, str(e), 'Failed')
      raise RuntimeError from e
  return make_response('')


def UploadRow(row):
  """
  Converts a Row entity into Skia Perf format and uploads it to Chromeperf GCS
  Bucket.

  Documentation on the Skia Perf format can be found here:
  https://skia.googlesource.com/buildbot/+/refs/heads/main/perf/FORMAT.md

  If the Row is from an internal test, it's uploaded to the
  'chrome-perf-non-public' public. Otherwise, it's uploaded to the
  'chrome-perf-public' bucket.

  Take for example a Row on commit position 12345 on the following public test:
  'ChromiumAndroid/android-cronet-arm-rel/resource_sizes (CronetSample.apk)/InstallSize/APK size'.

  It'll be uploaded to the following example path:
  'gs://chrome-perf-public/perf/2023/04/11/16/ChromiumAndroid/android-cronet-arm-rel/
  resource_sizes (CronetSample.apk)/InstallSize/APK size/12345/1681231603.3381824.json'

  Args:
    row: A Row entity.
  """

  # Currently, we only support rows with a Chromium commit position, as it's
  # the only format our Skia Perf instance can support.
  if not hasattr(row, 'r_commit_pos'):
    raise RuntimeError('Row has no Chromium commit position')

  test_path = utils.TestPath(row.parent_test)
  test_key = utils.TestKey(test_path)
  test = test_key.get()

  skia_data = _ConvertRowToSkiaPerf(row, test)

  internal_only = test.internal_only

  bucket_name = INTERNAL_BUCKET_NAME if internal_only else PUBLIC_BUCKET_NAME

  filename = '%s/%s/%s.json' % (test_path, str(row.r_commit_pos), time.time())
  filename = '/%s/perf/%s/%s' % (
      bucket_name, datetime.datetime.now().strftime('%Y/%m/%d/%H'), filename)

  gcs_file = cloudstorage.open(
      filename,
      'w',
      content_type='application/json',
      retry_params=cloudstorage.RetryParams(backoff_factor=1.1))

  gcs_file.write(json.dumps(skia_data))

  logging.info('Uploaded row to %s', filename)

  gcs_file.close()


def _ConvertRowToSkiaPerf(row, test):

  commit_position = row.r_commit_pos

  skia_data = {
      'version': 1,
      'git_hash': 'CP:%s' % str(commit_position),
      'key': {
          'master': test.master_name,
          'bot': test.bot_name,
          'benchmark': test.suite_name,
      },
      'results': [{
          'measurements': {
              'stat': _GetStatsForRow(row)
          },
          'key': _GetMeasurementKey(test)
      }],
      'links': _GetLinks(row)
  }

  return skia_data


def _GetStatsForRow(row):
  stats = []
  if not _IsNumber(row.value):
    raise RuntimeError('Row value is not a number. Value: %s' % row.value)
  stats.append({'value': 'value', 'measurement': row.value})

  if _IsNumber(row.error):
    stats.append({'value': 'error', 'measurement': row.error})
  if hasattr(row, 'd_count') and _IsNumber(row.d_count):
    stats.append({'value': 'count', 'measurement': row.d_count})
  if hasattr(row, 'd_max') and _IsNumber(row.d_max):
    stats.append({'value': 'max', 'measurement': row.d_max})
  if hasattr(row, 'd_min') and _IsNumber(row.d_min):
    stats.append({'value': 'min', 'measurement': row.d_min})
  if hasattr(row, 'd_sum') and _IsNumber(row.d_sum):
    stats.append({'value': 'sum', 'measurement': row.d_sum})
  if hasattr(row, 'd_std') and _IsNumber(row.d_std):
    stats.append({'value': 'std', 'measurement': row.d_std})
  if hasattr(row, 'd_avg') and _IsNumber(row.d_avg):
    stats.append({'value': 'avg', 'measurement': row.d_avg})

  return stats


def _GetMeasurementKey(test):
  measurement_key = {}

  measurement_key['improvement_direction'] = _GetImprovementDirection(
      test.improvement_direction)
  if test.units:
    measurement_key['unit'] = test.units
  if test.test_part1_name:
    measurement_key['test'] = test.test_part1_name
  if test.test_part2_name:
    measurement_key['subtest_1'] = test.test_part2_name
  if test.test_part3_name:
    measurement_key['subtest_2'] = test.test_part3_name
  if test.test_part4_name:
    measurement_key['subtest_3'] = test.test_part4_name
  if test.test_part5_name:
    measurement_key['subtest_4'] = test.test_part5_name
  if hasattr(test, 'test_part6_name') and test.test_part6_name:
    measurement_key['subtest_5'] = test.test_part6_name
  if hasattr(test, 'test_part7_name') and test.test_part7_name:
    measurement_key['subtest_6'] = test.test_part7_name
  if hasattr(test, 'test_part8_name') and test.test_part8_name:
    measurement_key['subtest_7'] = test.test_part8_name

  return measurement_key


def _GetLinks(row):
  links = {}

  # Annotations
  if hasattr(row, 'a_benchmark_config') and row.a_benchmark_config:
    links['Benchmark Config'] = row.a_benchmark_config
  if hasattr(row, 'a_build_uri') and row.a_build_uri:
    links['Build Page'] = row.a_build_uri
  if hasattr(row, 'a_tracing_uri') and row.a_tracing_uri:
    links['Tracing uri'] = row.a_tracing_uri
  if hasattr(row, 'a_stdio_uri') and row.a_stdio_uri:
    links['Test stdio'] = row.a_stdio_uri
  if hasattr(row, 'a_bot_id') and row.a_bot_id:
    links['Test bot'] = row.a_bot_id
  if hasattr(row, 'a_os_detail_vers') and row.a_os_detail_vers:
    links['OS Version'] = row.a_os_detail_vers
  if hasattr(row, 'a_default_rev') and row.a_default_rev:
    links['Default Revision'] = row.a_default_rev
  if hasattr(row, 'a_jobname') and row.a_jobname:
    links['Swarming Job Name'] = row.a_jobname

  # Revisions
  if hasattr(row, 'r_commit_pos') and row.r_commit_pos:
    links[
        'Chromium Commit Position'] = 'https://crrev.com/%s' % row.r_commit_pos
  if hasattr(row, 'r_chromium') and row.r_chromium:
    links['Chromium Git Hash'] = (
        'https://chromium.googlesource.com/chromium/src/+/%s' % row.r_chromium)
  if hasattr(row, 'r_v8_rev') and row.r_v8_rev:
    links[
        'V8 Git Hash'] = 'https://chromium.googlesource.com/v8/v8/+/%s' % row.r_v8_rev
  if hasattr(row, 'r_webrtc_git') and row.r_webrtc_git:
    links[
        'WebRTC Git Hash'] = 'https://webrtc.googlesource.com/src/+/%s' % row.r_webrtc_git
  if hasattr(row, 'r_chrome_version') and row.r_chrome_version:
    links['Chrome Version'] = (
        'https://chromium.googlesource.com/chromium/src/+/%s' %
        row.r_chrome_version)

  return links


def _GetImprovementDirection(v):

  if v == anomaly.UP:
    return 'up'
  if v == anomaly.DOWN:
    return 'down'
  if v == anomaly.UNKNOWN:
    return 'unknown'
  return None


def _IsNumber(v):
  return isinstance(v, (float, int))
