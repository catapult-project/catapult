# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Encapsulates a simplistic interface to the buildbucket service."""

import json

from apiclient import discovery

from dashboard import utils

_DISCOVERY_URL = (
    'https://cr-buildbucket.appspot.com'
    '/api/discovery/v1/apis/{api}/{apiVersion}/rest')

# Default Buildbucket bucket name.
_BUCKET_NAME = 'master.tryserver.chromium.perf'


def _DiscoverService(http):
  return discovery.build('buildbucket', 'v1',
                         discoveryServiceUrl=_DISCOVERY_URL, http=http)


def PutJob(job, bucket=_BUCKET_NAME):
  """Creates a job via buildbucket's API."""
  parameters = job.GetBuildParameters()
  service = _DiscoverService(utils.ServiceAccountHttp())
  request = service.put(
      body={
          'bucket': bucket,
          'parameters_json': json.dumps(parameters),
      })
  response_content = request.execute()
  job.response_fields = response_content.get('build')
  return job.response_fields.get('id')


def GetJobStatus(job_id):
  """Gets the details of a job via buildbucket's API."""
  service = _DiscoverService(utils.ServiceAccountHttp())
  request = service.get(id=job_id)
  response_content = request.execute()
  return response_content

# TODO(robertocn): Implement CancelJobByID
