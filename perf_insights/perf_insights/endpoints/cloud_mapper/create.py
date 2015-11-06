# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import os
import uuid
import webapp2

from google.appengine.api import taskqueue
from perf_insights.endpoints.cloud_mapper import job_info


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

class CreatePage(webapp2.RequestHandler):

  def get(self):
    self.response.headers['Content-Type'] = 'text/plain'

    mapper = self.request.get('mapper')
    reducer = self.request.get('reducer')
    query = self.request.get('query')
    corpus = self.request.get('corpus')
    revision = self.request.get('revision')
    if not revision:
      revision = 'HEAD'

    # TODO: Ned a nice way to initiate jobs with vulcanized mapper/reducer, so
    #  will just hardcode for now.
    mapper = _FAKE_FILE

    job_uuid = str(uuid.uuid4())
    job = job_info.JobInfo(id=job_uuid)
    job.remote_addr = os.environ["REMOTE_ADDR"]
    job.status = 'QUEUED'
    job.mapper = mapper
    job.reducer = reducer
    job.query = query
    job.corpus = corpus
    job.revision = revision
    job.put()

    response = {
        'status': True,
        'jobid': job_uuid
    }

    self.response.out.write(json.dumps(response))

    payload = {'jobid': job_uuid}
    taskqueue.add(url='/cloud_mapper/task', name=job_uuid, params=payload)


app = webapp2.WSGIApplication([('/cloud_mapper/create', CreatePage)])
