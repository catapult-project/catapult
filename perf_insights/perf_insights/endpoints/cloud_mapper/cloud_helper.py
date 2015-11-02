# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import io
import httplib2

from google.appengine.api import memcache
from googleapiclient import http
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from oauth2client.appengine import AppAssertionCredentials
from perf_insights.endpoints.cloud_mapper import gce_creation_info

_PROJECT_NAME = 'performance-insights'
_DEFAULT_ZONE = 'us-central1-f'
_DEFAULT_MACHINE_TYPE = 'n1-highcpu-32'
_DEFAULT_SOURCE_DISK_IMAGE = 'perf-insights-cloud-mapper-image-1'
_DEFAULT_SCOPE = 'https://www.googleapis.com/auth/cloud-platform'
_IMAGE_PATH = 'global/images/{image}'


class CloudHelper(object):
  def __init__(self):
    self.compute_ = self._create_gce_api()
    self.storage_ = self._create_storage_api()
    self.gce_info_ = gce_creation_info.GCECreationInfo.get_by_id(
        'gce_creation_info')
    if not self.gce_info_ or 1:
      self.gce_info_ = gce_creation_info.GCECreationInfo(id='gce_creation_info')
      self.gce_info_.source_disk_image = _DEFAULT_SOURCE_DISK_IMAGE
      self.gce_info_.machine_type = _DEFAULT_MACHINE_TYPE
      self.gce_info_.zone = _DEFAULT_ZONE
      self.gce_info_.put()

  def CreateGCE(self, gce_name, startup_script):
    config = {
        'name': gce_name,
        'machineType': 'zones/%s/machineTypes/%s' % (
            self.gce_info_.zone, self.gce_info_.machine_type),

        # Specify the boot disk and the image to use as a source.
        'disks': [
            {
                'boot': True,
                'autoDelete': True,
                'initializeParams': {
                    'sourceImage': _IMAGE_PATH.format(
                        image=self.gce_info_.source_disk_image)
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
                _DEFAULT_SCOPE
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

    return self.compute_.instances().insert(project=_PROJECT_NAME,
                                            zone=self.gce_info_.zone,
                                            body=config).execute()

  def DeleteGCE(self, gce_name):
    return self.compute_.instances().delete(
        project=_PROJECT_NAME,
        zone=self.gce_info_.zone,
        instance=gce_name).execute()

  def _create_gce_api(self):
    credentials = AppAssertionCredentials(
        scope='https://www.googleapis.com/auth/compute')
    authorized_http = credentials.authorize(httplib2.Http(memcache))
    compute = build("compute", "v1", http=authorized_http)

    return compute

  def _create_storage_api(self):
    credentials = AppAssertionCredentials(
        scope='https://www.googleapis.com/auth/storage')
    authorized_http = credentials.authorize(httplib2.Http(memcache))
    storage = build("storage", "v1", http=authorized_http)

    return storage

  def WriteGCS(self, fullurl, data):
    media = http.MediaIoBaseUpload(io.BytesIO(data), 'text/plain')

    bucket, path = self._split_gcs_name(fullurl)
    req = self.storage_.objects().insert(
        media_body=media, name=path, bucket=bucket)
    resp = req.execute()
    return resp

  def _split_gcs_name(self, full_url):
    stripped_url = full_url.split('gs://')[1].split('/')
    bucket = stripped_url[0]
    path = '/'.join(stripped_url[1:])
    return bucket, path

  def ReadGCS(self, fullurl):
    bucket, name = self._split_gcs_name(fullurl)
    req = self.storage_.objects().get_media(
        bucket=bucket, object=name)

    fh = io.BytesIO()
    downloader = http.MediaIoBaseDownload(fh, req, chunksize=1024*1024)

    while True:
      _, done = downloader.next_chunk()
      if done:
        return fh.getvalue()
    return None

  def ListGCS(self, fullurl):
    bucket, path = self._split_gcs_name(fullurl)
    req = self.storage_.objects().list(
        bucket=bucket, prefix=path)
    return req.execute()
