# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import logging
import os
import urllib
import uuid
import webapp2

from google.appengine.api import modules
from google.appengine.api import taskqueue
from google.appengine.api import urlfetch
from perf_insights.endpoints.cloud_mapper import job_info
from perf_insights import cloud_config

def _is_devserver():
  return os.environ.get('SERVER_SOFTWARE','').startswith('Development')

_FAKE_FILE = """
<!DOCTYPE html>
<!--
Copyright (c) 2015 The Chromium Authors. All rights reserved.
Use of this source code is governed by a BSD-style license that can be
found in the LICENSE file.
-->
<link rel="import" href="/perf_insights/function_handle.html">
<link rel="import" href="/perf_insights/value/value.html">
<link rel="import" href="/tracing/extras/rail/rail_score.html">

<script>
tr.exportTo('pi.m', function() {

  function railMapFunction(results, runInfo, model) {
    var railScore = tr.e.rail.RAILScore.fromModel(model);
    if (railScore === undefined) {
      return;
    }
    results.addValue(new pi.v.DictValue(runInfo, 'railScore',
                                        railScore.asDict()));
  }
  pi.FunctionRegistry.register(railMapFunction);

  return {
    railMapFunction: railMapFunction
  };
});

</script>
"""

class TestPage(webapp2.RequestHandler):

  def get(self):
    self.response.headers['Content-Type'] = 'text/plain'

    payload = {
        'mapper': _FAKE_FILE,
        'reducer': '',
        'query': 'MAX_TRACE_HANDLES=10',
        'corpus': cloud_config.Get().default_corpus,
        'revision': 'HEAD'
    }
    payload = urllib.urlencode(payload)
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-URLFetch-Service-Id': cloud_config.Get().urlfetch_service_id
    }

    url = "https://%s/cloud_mapper/create" % modules.get_hostname()
    # Silliness to make SSL validation work, when https is required.
    url = url.replace('.', '-dot-', url.count('.') - 2)
    if _is_devserver():
        url = 'http://localhost:8080/cloud_mapper/create'

    logging.info('Sending create request to URL: %s' % url)

    result = urlfetch.fetch(url=url, payload=payload,
        method=urlfetch.POST, headers=headers, follow_redirects=False,
        deadline=60)
    self.response.out.write(result.content)


app = webapp2.WSGIApplication([('/cloud_mapper/test', TestPage)])
