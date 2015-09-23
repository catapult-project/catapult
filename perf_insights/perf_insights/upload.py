# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import re
import webapp2
import uuid

from perf_insights import trace_info

import third_party.cloudstorage as gcs

from google.appengine.api import app_identity

default_retry_params = gcs.RetryParams(initial_delay=0.2,
                                       max_delay=5.0,
                                       backoff_factor=2,
                                       max_retry_period=15)
gcs.set_default_retry_params(default_retry_params)


class UploadPage(webapp2.RequestHandler):

  def get(self):
    self.response.out.write("""
          <html><body>
            <head><title>Performance Insights - Trace Uploader</title></head>
            <form action="/upload" enctype="multipart/form-data" method="post">
              <div><input type="file" name="trace"/></div>
              <div><input type="submit" value="Upload"></div>
            </form><hr>
          </body></html>""")

  def post(self):
    trace_uuid = str(uuid.uuid4())
    if 'GCS_BUCKET_NAME' not in os.environ:
      bucket_name = app_identity.get_default_gcs_bucket_name()
    else:
      bucket_name = os.environ['GCS_BUCKET_NAME']
    gcs_path = ('/' + bucket_name + '/' + trace_uuid + '.gz')
    gcs_file = gcs.open(gcs_path,
                        'w',
                        content_type='application/octet-stream',
                        options={},
                        retry_params=default_retry_params)
    gcs_file.write(self.request.get('trace'))
    gcs_file.close()

    trace_object = trace_info.TraceInfo(id=trace_uuid)
    trace_object.prod = self.request.get('prod')
    trace_object.network_type = self.request.get('network_type')
    trace_object.remote_addr = os.environ["REMOTE_ADDR"]
    tags_string = self.request.get('tags')
    if tags_string:
      # Tags are comma separated and should only include alphanumeric + '-'.
      if re.match('^[a-zA-Z0-9-,]+$', tags_string):
        trace_object.tags = tags_string.split(',')
      else:
        logging.warning('The provided tags string includes one or more invalid'
                        ' characters and will be ignored')
    trace_object.user_agent = self.request.headers.get('User-Agent')
    trace_object.ver = self.request.get('product_version')
    trace_object.put()

    self.response.write(trace_uuid)

app = webapp2.WSGIApplication([('/upload', UploadPage)])
