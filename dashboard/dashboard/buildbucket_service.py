# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Encapsulates a simplistic interface to the buildbucket service."""

import json

from apiclient import discovery
import httplib2

from dashboard import utils

_DISCOVERY_URL = (
    'https://cr-buildbucket.appspot.com'
    '/_ah/api/discovery/v1/apis/{api}/{apiVersion}/rest')

# Default Buildbucket bucket name.
_BUCKET_NAME = 'master.tryserver.chromium.perf'


def _DiscoverService():
  return discovery.build('buildbucket', 'v1',
                         discoveryServiceUrl=_DISCOVERY_URL)


class _AuthenticatedHttp(object):
  """Provides access via its constructor to a singleton authenticated http."""

  _singleton = None
  _singleton_credentials = None

  def __new__(cls, credentials):
    if credentials and credentials != cls._singleton_credentials:
      cls._singleton_credentials = credentials
      cls._MakeSingleton(credentials)
    if not cls._singleton:
      cls._MakeSingleton()
    assert cls._singleton
    return cls._singleton

  @classmethod
  def _MakeSingleton(cls, override_credentials=None):
    """Instantiates the singleton."""
    # Uses rietveld credentials to authorize an http client. Note this same
    # account is authorized for buildbucket.
    cls._singleton = httplib2.Http()
    if override_credentials:
      credentials = override_credentials
    else:
      credentials = utils.ServiceAccountCredentials()

    # If we cannot pull the credentials from ndb we simply use the unauthorized
    # client. This useful when running a local dev server.
    if credentials:
      credentials.authorize(cls._singleton)


def PutJob(job, bucket=_BUCKET_NAME, credentials=None):
  """Creates a job via buildbucket's API."""
  parameters = job.GetBuildParameters()
  service = _DiscoverService()
  request = service.put(
      body={
          'bucket': bucket,
          'parameters_json': json.dumps(parameters),
      })
  response_content = request.execute(http=_AuthenticatedHttp(credentials))
  job.response_fields = response_content.get('build')
  return job.response_fields.get('id')


def GetJobStatus(job_id, credentials=None):
  """Gets the details of a job via buildbucket's API."""
  service = _DiscoverService()
  request = service.get(id=job_id)
  response_content = request.execute(http=_AuthenticatedHttp(credentials))
  return response_content

# TODO(robertocn): Implement CancelJobByID
