# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Encapsulates a simplistic interface to the buildbucket service."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import json
import re
import uuid

from dashboard.services import request
from dashboard.common import utils

API_BASE_URL = 'https://cr-buildbucket.appspot.com/api/buildbucket/v1/'
API_BASE_URL2 = 'https://cr-buildbucket.appspot.com/prpc/buildbucket.v2.Builds/'

# Default Buildbucket bucket name.
_BUCKET_NAME = 'master.tryserver.chromium.perf'

_BUCKET_RE = re.compile(r'luci\.([^.]+)\.([^.]+)')

def Put(bucket, tags, parameters):
  if utils.IsRunningBuildBucketV2():
    return PutV2(bucket, tags, parameters)
  return PutV1(bucket, tags, parameters)


def PutV1(bucket, tags, parameters, pubsub_callback=None):
  body = {
      'bucket': bucket,
      'tags': tags,
      'parameters_json': json.dumps(parameters, separators=(',', ':')),
  }
  if pubsub_callback:
    body['pubsub_callback'] = pubsub_callback
  return request.RequestJson(API_BASE_URL + 'builds', method='PUT', body=body)


def PutV2(bucket, tags, parameters):
  bucket_parts = _BUCKET_RE.split(bucket)
  if len(bucket_parts) != 4:
    raise ValueError('Could not parse bucket value: %s' % bucket)
  project = bucket_parts[1]
  bucket = bucket_parts[2]
  body = {
      'request_id': str(uuid.uuid4()),
      'builder': {
          'project': project,
          'bucket': bucket,
          'builder': parameters['builder_name'],
      },
      # Make sure 'tags' gets formatted like StringPair expects:
      # [{'key': key, 'value'; value}]
      'tags':  [{'key': v[0], 'value': v[1]} for v in [
          e.split(':') for e in tags]],
      'properties': parameters.get('properties', {}),
  }
  logging.info("bbv2 Put body: \n%s\n", json.dumps(body))

  return request.RequestJson(
      API_BASE_URL2 + 'ScheduleBuild', method='POST', body=body)


def GetJobStatus(job_id):
  if utils.IsRunningBuildBucketV2():
    return GetJobStatusV2(job_id)
  return GetJobStatusV1(job_id)


def GetJobStatusV1(job_id):
  """Gets the details of a job via buildbucket's API."""
  return request.RequestJson(API_BASE_URL + 'builds/%s' % (job_id))


# TODO: Rename to Get().
def GetJobStatusV2(job_id):
  """Gets the details of a job via buildbucket's API."""
  body = json.dumps({
      'id': job_id
  })
  return request.RequestJson(
      API_BASE_URL2 + 'GetBuild', method='POST', body=body)


# TODO(robertocn): Implement CancelJobByID
