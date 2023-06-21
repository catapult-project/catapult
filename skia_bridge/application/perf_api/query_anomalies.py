# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
import datetime

from flask import Blueprint, request, make_response
import logging
import json

from common import cloud_metric
from application.perf_api import datastore_client, auth_helper

from google.cloud import datastore

blueprint = Blueprint('query_anomalies', __name__)


ALLOWED_CLIENTS = [
    # TODO: Remove the user accounts below once skia service account
    #       is validated.
    'ashwinpv@google.com',
    'sunpeng@google.com',
    'funing@google.com',
    'eduardoyap@google.com',
    # Chrome (public) skia instance service account
    'perf-chrome-public@skia-infra-public.iam.gserviceaccount.com',
    'perf-chrome-internal@skia-infra-corp.iam.gserviceaccount.com',
]

DATASTORE_TEST_BATCH_SIZE = 25

def Serialize(value):
  if isinstance(value, datetime.datetime):
    return str(value)

  return value.__dict__


class AnomalyData:
  test_path:str
  start_revision:int
  end_revision:int
  id:int
  timestamp:datetime.datetime
  bug_id:int
  is_improvement:bool
  recovered:bool
  state:str
  statistic:str
  units:str
  degrees_of_freedom:float
  median_before_anomaly:float
  median_after_anomaly:float
  p_value:float
  segment_size_after:int
  segment_size_before:int
  std_dev_before_anomaly:float
  t_statistic:float

  def __init__(
      self,
      **kwargs):
    self.__dict__.update(kwargs)

class AnomalyResponse:
  def __init__(self):
    self.anomalies = {}

  def AddAnomaly(self, test_name: str, anomaly_data:AnomalyData):
    if not self.anomalies.get(test_name):
      self.anomalies[test_name] = []

    self.anomalies[test_name].append(anomaly_data.__dict__)

  def ToDict(self):
    return {
      "anomalies": {
          test_name: self.anomalies[test_name] for test_name in self.anomalies
      }
    }

@blueprint.route('/find', methods=['POST'])
@cloud_metric.APIMetric("skia-bridge", "/anomalies/find")
def QueryAnomaliesPostHandler():
  try:
    logging.info('Received query request with data %s', request.data)
    is_authorized = auth_helper.AuthorizeBearerToken(request, ALLOWED_CLIENTS)
    if not is_authorized:
      return 'Unauthorized', 401
    try:
      data = json.loads(request.data)
    except json.decoder.JSONDecodeError:
      return 'Malformed Json', 400

    is_valid, error = ValidateRequest(data)
    if not is_valid:
      return error, 400

    client = datastore_client.DataStoreClient()
    batched_tests = list(CreateTestBatches(data['tests']))
    logging.info('Created %i batches for DataStore query', len(batched_tests))
    anomalies = []
    for batch in batched_tests:
      batch_anomalies = client.QueryAnomalies(
        batch, data['min_revision'], data['max_revision'])
      if batch_anomalies and len(batch_anomalies) > 0:
        anomalies.extend(batch_anomalies)

    logging.info('%i anomalies returned from DataStore', len(anomalies))
    response = AnomalyResponse()
    for found_anomaly in anomalies:
      anomaly_data = GetAnomalyData(found_anomaly)
      response.AddAnomaly(anomaly_data.test_path, anomaly_data)

    return make_response(response.ToDict())
  except Exception as e:
    logging.exception(e)
    raise


def CreateTestBatches(testList):
  for i in range(0, len(testList), DATASTORE_TEST_BATCH_SIZE):
    yield testList[i:i + DATASTORE_TEST_BATCH_SIZE]


def TestPath(key: datastore.key.Key):
  if key.kind == 'Test':
    # The Test key looks like ('Master', 'name', 'Bot', 'name', 'Test' 'name'..)
    # Pull out every other entry and join with '/' to form the path.
    return '/'.join(key.flat()[1::2])

  assert key.kind == 'TestMetadata' or key.kind == 'TestContainer'
  return key.id_or_name


def GetAnomalyData(anomaly_obj):
  bug_id = anomaly_obj.get('bug_id')

  if bug_id is None:
    bug_id = '-1'

  return AnomalyData(
      test_path=TestPath(anomaly_obj.get('test')),
      start_revision=anomaly_obj.get('start_revision'),
      end_revision=anomaly_obj.get('end_revision'),
      timestamp=anomaly_obj.get('timestamp'),
      id=anomaly_obj.id,
      bug_id=int(bug_id),
      is_improvement=anomaly_obj.get('is_improvement'),
      recovered=anomaly_obj.get('recovered'),
      state=anomaly_obj.get('state'),
      statistic=anomaly_obj.get('statistic'),
      units=anomaly_obj.get('units'),
      degrees_of_freedom=anomaly_obj.get('degrees_of_freedom'),
      median_before_anomaly=anomaly_obj.get('median_before_anomaly'),
      median_after_anomaly=anomaly_obj.get('median_after_anomaly'),
      p_value=anomaly_obj.get('p_value'),
      segment_size_after=anomaly_obj.get('segment_size_after'),
      segment_size_before=anomaly_obj.get('segment_size_before'),
      std_dev_before_anomaly=anomaly_obj.get('std_dev_before_anomaly'),
      t_statistic=anomaly_obj.get('t_statistic'),
  )

def ValidateRequest(request_data):
  required_keys = ['tests', 'min_revision', 'max_revision']
  missing_keys = []
  for key in required_keys:
    if not request_data.get(key):
      missing_keys.append(key)

  error = None
  result = True
  if len(missing_keys) > 0:
    result = False
    error = 'Required parameters %s missing from the request.' % missing_keys

  return result, error
