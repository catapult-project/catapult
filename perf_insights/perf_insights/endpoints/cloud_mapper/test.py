# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import os
import urllib
import uuid
import webapp2

from google.appengine.api import taskqueue
from google.appengine.api import urlfetch
from perf_insights.endpoints.cloud_mapper import job_info


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
        'corpus': 'http://performance-insights.appspot.com',
        'revision': 'HEAD'
    }
    payload = urllib.urlencode(payload)
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    url = 'http://performance-insights.appspot.com/cloud_mapper/create'
    if _is_devserver():
        url = 'http://localhost:8080/cloud_mapper/create'

    result = urlfetch.fetch(url=url, payload=payload,
        method=urlfetch.POST, headers=headers)
    self.response.out.write(result.content)


app = webapp2.WSGIApplication([('/cloud_mapper/test', TestPage)])
