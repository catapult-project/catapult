# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
import datetime

from flask import make_response, Blueprint, request, jsonify
import logging
import json

from dashboard.models import anomaly
from dashboard.common import utils

blueprint = Blueprint('query_anomalies', __name__)


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

  def __init__(
      self,
      **kwargs):
    self.__dict__.update(kwargs)

  def ToJson(self):
    return json.dumps(self, default=Serialize)


@blueprint.route('/find', methods=['POST'])
def QueryAnomaliesPostHandler():
  try:
    logging.info('Received query request with data %s', request.data)
    data = json.loads(request.data)
    test_keys = [utils.TestKey(test_path) for test_path in data['tests']]
    anomalies, _, _ = anomaly.Anomaly.QueryAsync(
        test_keys=test_keys,
        max_start_revision=data['max_revision'],
        min_end_revision=data['min_revision']).get_result()

    logging.info('%i anomalies found for the request.', len(anomalies))
    response = {}
    for found_anomaly in anomalies:
      anomaly_data = GetAnomalyData(found_anomaly)
      if not response.get(anomaly_data.test_path):
        response[anomaly_data.test_path] = []

      response[anomaly_data.test_path].append(anomaly_data.ToJson())

    return jsonify(response)
  except Exception as e:
    logging.exception(e)
    raise


@blueprint.route('/', methods=['GET'])
def QueryAnomaliesGetHandler():
  """ Required for service health check """
  return make_response('Ok')


def GetAnomalyData(anomaly_obj: anomaly.Anomaly):
  return AnomalyData(
      test_path=utils.TestPath(anomaly_obj.test),
      start_revision=anomaly_obj.start_revision,
      end_revision=anomaly_obj.end_revision,
      timestamp=anomaly_obj.timestamp
  )
