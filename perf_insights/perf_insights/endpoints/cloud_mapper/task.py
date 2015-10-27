# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import httplib2
import json
import logging
import urllib
import uuid
import webapp2

from google.appengine.api import memcache
from google.appengine.api import urlfetch
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from oauth2client.appengine import AppAssertionCredentials

from perf_insights.endpoints.cloud_mapper import gce_creation_info
from perf_insights.endpoints.cloud_mapper import job_info
import third_party.cloudstorage as gcs


_DEFAULT_TARGET = 'test'
_DEFAULT_ZONE = 'us-central1-f'
_DEFAULT_MACHINE_TYPE = 'n1-standard-1'
_DEFAULT_SOURCE_DISK_IMAGE = 'perf-insights-cloud-mapper-image-1'
_PROJECT_NAME = 'performance-insights'
_DEFAULT_BUCKET = '/performance-insights-cloud-mapper/%s/jobs/{name}' % (
    _DEFAULT_TARGET)
_PERFORMANCE_INSIGHTS_URL = 'https://performance-insights.appspot.com'

_IMAGE_PATH = 'global/images/{image}'
_STARTUP_SCRIPT = \
"""#!/bin/bash
cd /catapult
git pull
git checkout {revision}
"""


class TaskPage(webapp2.RequestHandler):

  def _CreateGCEInstace(self, api, gce_name, startup_script):
    gce_info = gce_creation_info.GCECreationInfo.get_by_id('gce_creation_info')
    if not gce_info:
      gce_info = gce_creation_info.GCECreationInfo(id='gce_creation_info')
      gce_info.source_disk_image = _DEFAULT_SOURCE_DISK_IMAGE
      gce_info.machine_type = _DEFAULT_MACHINE_TYPE
      gce_info.zone = _DEFAULT_ZONE
      gce_info.put()

    config = {
        'name': gce_name,
        'machineType': 'zones/%s/machineTypes/%s' % (
            gce_info.zone, gce_info.machine_type),

        # Specify the boot disk and the image to use as a source.
        'disks': [
            {
                'boot': True,
                'autoDelete': True,
                'initializeParams': {
                    'sourceImage': _IMAGE_PATH.format(
                        image=gce_info.source_disk_image)
                }
            }
        ],

        # Specify a network interface with NAT to access the public
        # internet.
        'networkInterfaces': [{
            'network': 'global/networks/default',
            'accessConfigs': [
                {'type': 'ONE_TO_ONE_NAT', 'name': 'External NAT'}
            ]
        }],

        # Allow the instance to access cloud storage and logging.
        'serviceAccounts': [{
            'email': 'default',
            'scopes': [
                'https://www.googleapis.com/auth/cloud-platform'
            ]
        }],

        # Metadata is readable from the instance and allows you to
        # pass configuration from deployment scripts to instances.
        'metadata': {
            'items': [{
                # Startup script is automatically executed by the
                # instance upon startup.
                'key': 'startup-script',
                'value': startup_script
            }]
        }
    }

    return api.instances().insert(project=_PROJECT_NAME,
                                  zone=gce_info.zone,
                                  body=config).execute()

  def post(self):
    self.response.headers['Content-Type'] = 'text/plain'

    jobid = self.request.get('jobid')
    job = job_info.JobInfo.get_by_id(jobid)
    if not job:
      return

    payload = urllib.urlencode({'q': 'MAX_TRACE_HANDLES=10'})
    query_url = '%s/query?%s' % (_PERFORMANCE_INSIGHTS_URL, payload)
    result = urlfetch.fetch(url=query_url,
                            payload=payload,
                            method=urlfetch.GET,
                            follow_redirects=False,
                            deadline=10)
    logging.info(result.content)

    taskid = str(uuid.uuid4())
    traces = json.loads(result.content)

    default_retry_params = gcs.RetryParams(initial_delay=0.2,
                                           max_delay=5.0,
                                           backoff_factor=2,
                                           max_retry_period=15)
    gcs_file = gcs.open(_DEFAULT_BUCKET.format(name=taskid),
                        'w',
                        content_type='text/plain',
                        options={},
                        retry_params=default_retry_params)
    gcs_file.write(json.dumps(traces))
    gcs_file.close()

    credentials = AppAssertionCredentials(
        scope='https://www.googleapis.com/auth/compute')
    http = credentials.authorize(httplib2.Http(memcache))
    compute = build("compute", "v1", http=http)

    startup_script = _STARTUP_SCRIPT.format(
        revision=job.revision)

    result = self._CreateGCEInstace(
        compute, 'mr-%s' % jobid, startup_script)

    logging.info('Call to instances().insert response:\n')
    for k, v in sorted(result.iteritems()):
        logging.info(' %s: %s' % (k, v))

    job.status = 'COMPLETE'
    job.put()

    response = {'success': False}
    self.response.out.write(json.dumps(response))


app = webapp2.WSGIApplication([('/cloud_mapper/task', TaskPage)])
