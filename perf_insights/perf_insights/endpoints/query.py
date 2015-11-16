# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import os
import webapp2

from perf_insights import cloud_config
from perf_insights import corpus_query
from perf_insights import trace_info

from google.appengine.api import app_identity


def _bucket_name():
  if 'GCS_BUCKET_NAME' not in os.environ:
    return app_identity.get_default_gcs_bucket_name()
  return os.environ['GCS_BUCKET_NAME']


class QueryPage(webapp2.RequestHandler):

  def get(self):
    self.response.headers['Content-Type'] = 'text/plain'
    raw_query = self.request.get('q')
    if not raw_query:
      raw_query = 'MAX_TRACE_HANDLES=100'

    query = corpus_query.CorpusQuery.FromString(raw_query)
    (gql, args) = query.AsGQLWhereClause()
    reports = trace_info.TraceInfo.gql(gql, *args)
    reports_json = json.dumps(
      ['gs://%s/%s.gz' % (cloud_config.Get().trace_upload_bucket,
          i.key.string_id()) for i in reports])

    self.response.out.write(reports_json)

app = webapp2.WSGIApplication([('/query', QueryPage)])
