# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Encapsulates a simplistic interface to the buildbucket service."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json

from dashboard.services import request


API_BASE_URL = 'https://cr-buildbucket.appspot.com/api/buildbucket/v1/'

# Default Buildbucket bucket name.
_BUCKET_NAME = 'master.tryserver.chromium.perf'


def Put(bucket, tags, parameters, pubsub_callback=None):
  body = {
      'bucket': bucket,
      'tags': tags,
      'parameters_json': json.dumps(parameters, separators=(',', ':')),
  }
  if pubsub_callback:
    body['pubsub_callback'] = pubsub_callback
  return request.RequestJson(API_BASE_URL + 'builds', method='PUT', body=body)

# TODO: Deprecated. Use Put() instead.
def PutJob(job, bucket=_BUCKET_NAME):
  """Creates a job via buildbucket's API."""
  parameters = job.GetBuildParameters()
  response_content = Put(bucket, [], parameters)
  job.response_fields = response_content.get('build')
  return job.response_fields.get('id')


# TODO: Rename to Get().
def GetJobStatus(job_id):
  """Gets the details of a job via buildbucket's API."""
  return request.RequestJson(API_BASE_URL + 'builds/%s' % (job_id))


# TODO(robertocn): Implement CancelJobByID
