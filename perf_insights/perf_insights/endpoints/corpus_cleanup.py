# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import logging
import webapp2

from perf_insights import cloud_config
from perf_insights.endpoints.cloud_mapper.cloud_helper import \
    default_retry_params
from perf_insights.trace_info import TraceInfo
import cloudstorage as gcs

BATCH_SIZE = 100
MAX_DAYS = 30


class CorpusCleanupPage(webapp2.RequestHandler):

  def _delete_traces(self):
    trace_bucket = cloud_config.Get().trace_upload_bucket
    deleted_traces = 0

    oldest_time = datetime.datetime.now() - datetime.timedelta(days=MAX_DAYS)
    q = TraceInfo.query(TraceInfo.date < oldest_time)

    for key in q.fetch(BATCH_SIZE, keys_only=True):
      gcs_path = '/%s/%s.gz' % (trace_bucket, key.id())
      try:
        gcs.delete(gcs_path, retry_params=default_retry_params)
      except gcs.NotFoundError:
        pass

      key.delete()
      deleted_traces += 1

    return deleted_traces

  def get(self):
    self.response.out.write('<html><body>')

    while True:
      deleted_traces = self._delete_traces()
      self.response.out.write("<br><div><bold>Traces Cleaned:</bold> %s</div>"
          % deleted_traces)

      logging.info('Daily cleanup deleted %s traces.' % deleted_traces)

      if deleted_traces < BATCH_SIZE:
        break

    self.response.out.write('</body></html>')


app = webapp2.WSGIApplication([('/corpus_cleanup', CorpusCleanupPage)])
