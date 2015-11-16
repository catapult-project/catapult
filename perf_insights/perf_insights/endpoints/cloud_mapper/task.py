# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import logging
import time
import urllib
import uuid
import webapp2

from google.appengine.api import urlfetch
from perf_insights.endpoints.cloud_mapper import cloud_helper
from perf_insights.endpoints.cloud_mapper import job_info
from perf_insights import cloud_config

_STARTUP_SCRIPT = \
"""#!/bin/bash
cd /catapult
git pull
git checkout {revision}

perf_insights/bin/gce_instance_map_job --jobs=32\
 {mapper} {path}{gcs} {path}{gcs}.result
"""


class TaskPage(webapp2.RequestHandler):

  def _QueryForTraces(self, corpus, query):
    payload = urllib.urlencode({'q': query})
    query_url = '%s/query?%s' % (corpus, payload)

    headers = {
        'X-URLFetch-Service-Id': cloud_config.Get().urlfetch_service_id
    }

    result = urlfetch.fetch(url=query_url,
                            payload=payload,
                            method=urlfetch.GET,
                            headers=headers,
                            follow_redirects=False,
                            deadline=10)
    logging.info(result.content)

    return json.loads(result.content)

  def _DispatchTracesAndWaitForResult(self, job, traces, num_instances):
    def _slice_it(li, cols=2):
      start = 0
      for i in xrange(cols):
          stop = start + len(li[i::cols])
          yield li[start:stop]
          start = stop

    tasks = []

    helper = cloud_helper.CloudHelper()

    # TODO(simonhatch): In the future it might be possibly to only specify a
    # reducer and no mapper. Revisit this.
    bucket_path = cloud_config.Get().control_bucket_path + "/jobs/"
    mapper_url = '%s%s.mapper' % (bucket_path, job.key.id())
    mapper_text = job.mapper.encode('ascii', 'ignore')
    helper.WriteGCS(mapper_url, mapper_text)

    # Split the traces up into N buckets.
    for current_traces in _slice_it(traces, num_instances):
      taskid = str(uuid.uuid4())
      current_task = {
          'id': taskid,
          'gce_name': 'mr-%s' % taskid
      }

      helper.WriteGCS(bucket_path + taskid, json.dumps(current_traces))

      startup_script = _STARTUP_SCRIPT.format(revision=job.revision,
                                              gcs=taskid,
                                              path=bucket_path,
                                              mapper=mapper_url)

      result = helper.CreateGCE(current_task['gce_name'], startup_script)

      logging.info('Call to instances().insert response:\n')
      for k, v in sorted(result.iteritems()):
        logging.info(' %s: %s' % (k, v))

      tasks.append(current_task)

    return self._WaitOnResults(helper, tasks)

  def _WaitOnResults(self, helper, tasks):
    # TODO: There's no reducer yet, so we can't actually collapse multiple
    # results into one results file.
    results = None
    while tasks:
      for current_task in tasks:
        task_results_path = '%s/jobs/%s.result' % (
            cloud_config.Get().control_bucket_path, current_task['id'])
        has_result = helper.ListGCS(task_results_path)
        if has_result.get('items'):
          logging.info(str(has_result))
          results = task_results_path
          helper.DeleteGCE(current_task['gce_name'])
          tasks.remove(current_task)
      time.sleep(1)
    logging.info("Finished all tasks.")
    return results

  def _RunMappers(self, job):
    # TODO(simonhatch): Figure out the optimal # of instances to spawn.
    num_instances = 1

    # Get all the traces to process
    traces = self._QueryForTraces(job.corpus, job.query)

    return self._DispatchTracesAndWaitForResult(job, traces, num_instances)

  def post(self):
    self.response.headers['Content-Type'] = 'text/plain'

    jobid = self.request.get('jobid')
    job = job_info.JobInfo.get_by_id(jobid)
    if not job:
      return

    if job.status != 'QUEUED':
      return

    job.status = 'IN_PROGRESS'
    job.put()

    try:
      results_url = self._RunMappers(job)

      job.status = 'COMPLETE'
      job.results = results_url
      job.put()
    except Exception as e:
      job.status = 'ERROR'
      job.put()
      logging.exception('Failed job: %s' % e.message)


app = webapp2.WSGIApplication([('/cloud_mapper/task', TaskPage)])
