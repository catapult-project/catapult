# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
import datetime

from flask import Blueprint, request, make_response
import logging
import json
import uuid

from common import cloud_metric, utils
from application.perf_api import datastore_client, auth_helper


blueprint = Blueprint('anomalies', __name__)


ALLOWED_CLIENTS = [
    # Chrome (public) skia instance service account
    'perf-chrome-public@skia-infra-public.iam.gserviceaccount.com',
    # Chrome (internal) skia instance service account
    'perf-chrome-internal@skia-infra-corp.iam.gserviceaccount.com',
    # WebRTC (public) skia instance service account
    'perf-webrtc-public@skia-infra-public.iam.gserviceaccount.com',
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
    is_authorized, _ = auth_helper.AuthorizeBearerToken(
      request, ALLOWED_CLIENTS)
    if not is_authorized:
      return 'Unauthorized', 401
    try:
      data = json.loads(request.data)
    except json.decoder.JSONDecodeError:
      return 'Malformed Json', 400

    is_valid, error = ValidateRequest(
      data,
      ['tests', 'min_revision', 'max_revision'])
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

@blueprint.route('/add', methods=['POST'], endpoint='AddAnomalyPostHandler')
@cloud_metric.APIMetric("skia-bridge", "/anomalies/add")
def AddAnomalyPostHandler():
  try:
    logging.info('Received query request with data %s', request.data)
    is_authorized, _ = auth_helper.AuthorizeBearerToken(
      request, ALLOWED_CLIENTS)
    if not is_authorized:
      return 'Unauthorized', 401
    try:
      data = json.loads(request.data)
    except json.decoder.JSONDecodeError:
      return 'Malformed Json', 400

    required_keys = ['start_revision', 'end_revision', 'project_id',
                     'test_path', 'is_improvement', 'bot_name',
                     'internal_only']
    # TODO: Make the below keys required once the changes are rolled
    # out in to skia perf
    optional_keys = ['median_before_anomaly', 'median_after_anomaly']
    is_valid, error = ValidateRequest(data, required_keys)
    if not is_valid:
      return error, 400

    test_path = data['test_path']
    # Create the anomaly entity with the required data
    required_keys.remove('test_path')
    anomaly_data = {key : data[key] for key in required_keys}
    anomaly_data.update(GetTestFieldsFromPath(test_path))
    anomaly_data['timestamp'] = datetime.datetime.utcnow()
    anomaly_data['source'] = 'skia'

    for optional_key in optional_keys:
      if data.get(optional_key, None):
        anomaly_data[optional_key] = data[optional_key]

    _ExtendRevisions(anomaly_data)
    client = datastore_client.DataStoreClient()
    anomaly = client.CreateEntity(datastore_client.EntityType.Anomaly,
                                  str(uuid.uuid4()),
                                  anomaly_data)
    test_metadata = client.GetEntity(datastore_client.EntityType.TestMetadata,
                                     test_path)
    anomaly['test'] = test_metadata.key

    skia_ungrouped_name = 'Ungrouped_Skia'
    ungrouped_type = 2 # 2 is the type for "ungrouped" groups
    alert_groups = client.QueryAlertGroups(skia_ungrouped_name, ungrouped_type)
    if not alert_groups:
      ungrouped_data = {
        'project_id': anomaly_data['project_id'],
        'group_type': ungrouped_type,
        'active': True,
        'anomalies': [anomaly.key],
        'name': skia_ungrouped_name,
        'created': datetime.datetime.utcnow(),
        'updated': datetime.datetime.utcnow()
      }
      alert_group = client.CreateEntity(datastore_client.EntityType.AlertGroup,
                                         str(uuid.uuid4()),
                                         ungrouped_data,
                                         save=True)
    else:
      alert_group = alert_groups[0]
      group_anomalies = alert_group.get('anomalies', [])
      group_anomalies.append(anomaly.key)
      alert_group['anomalies'] = group_anomalies
      alert_group['updated'] = datetime.datetime.utcnow()

    anomaly['groups'] = [alert_group]

    client.PutEntities([anomaly, alert_group], transaction=True)
    return {
      'anomaly_id': anomaly.key.id_or_name,
      'alert_group_id': alert_group.key.id_or_name
    }
  except Exception as e:
    logging.exception(e)
    raise


def CreateTestBatches(testList):
  for i in range(0, len(testList), DATASTORE_TEST_BATCH_SIZE):
    yield testList[i:i + DATASTORE_TEST_BATCH_SIZE]

def GetAnomalyData(anomaly_obj):
  bug_id = anomaly_obj.get('bug_id')

  if bug_id is None:
    bug_id = '-1'

  return AnomalyData(
      test_path=utils.TestPath(anomaly_obj.get('test')),
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

def ValidateRequest(request_data, required_keys):
  missing_keys = []
  for key in required_keys:
    value = request_data.get(key, None)
    # Not using "if not value" since value can be boolean False
    if value == None:
      missing_keys.append(key)

  error = None
  result = True
  if len(missing_keys) > 0:
    result = False
    error = 'Required parameters %s missing from the request.' % missing_keys

  return result, error

def GetTestFieldsFromPath(test_path: str):
  # The test path is in the form master/bot/benchmark/test/...
  test_fields = {}
  test_parts = test_path.split('/')
  if len(test_parts) < 4:
    raise ValueError("Test path needs at least 4 parts")

  test_keys = ['master_name', 'bot_name', 'benchmark_name']
  for i in range(len(test_keys)):
    test_fields[test_keys[i]] = test_parts[i]
  return test_fields

def _ExtendRevisions(anomaly_data):
  start_revision = int(anomaly_data['start_revision']) - 5
  end_revision = int(anomaly_data['end_revision']) + 5

  anomaly_data['start_revision'] = start_revision
  anomaly_data['end_revision'] = end_revision
