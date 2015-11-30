# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import logging
import os
import time
import urllib
import uuid
import webapp2

from google.appengine.api import taskqueue
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

    # TODO(simonhatch): In the future it might be possibly to only specify a
    # reducer and no mapper. Revisit this.
    bucket_path = cloud_config.Get().control_bucket_path + "/jobs/"
    mapper_url = '%s%s.mapper' % (bucket_path, job.key.id())
    mapper_text = job.mapper.encode('ascii', 'ignore')
    cloud_helper.WriteGCS(mapper_url, mapper_text)

    version = self._GetVersion()

    tasks = {}

    # Split the traces up into N buckets.
    for current_traces in _slice_it(traces, num_instances):
      task_id = str(uuid.uuid4())

      payload = {
          'revision': job.revision,
          'traces': json.dumps(current_traces),
          'result': '%s%s.result' % (bucket_path, task_id),
          'mapper': mapper_url,
          'mapper_function': job.mapper_function
      }
      taskqueue.add(
          queue_name='mapper-queue',
          url='/cloud_worker/task',
          target=version,
          name=task_id,
          params=payload)
      tasks[task_id] = {'status': 'IN_PROGRESS'}

    # On production servers, we could just sit and wait for the results, but
    # dev_server is single threaded and won't run any other tasks until the
    # current one is finished. We'll just do the easy thing for now and
    # queue a task to check for the result.
    taskqueue.add(
        queue_name='default',
        url='/cloud_mapper/task',
        target=version,
        countdown=1,
        params={'jobid': job.key.id(),
                'type': 'check',
                'tasks': json.dumps(tasks)})

  def _GetVersion(self):
    version = os.environ['CURRENT_VERSION_ID'].split('.')[0]
    if cloud_config._is_devserver():
      version = taskqueue.DEFAULT_APP_VERSION
    return version

  def _CheckOnResults(self, job):
    tasks = json.loads(self.request.get('tasks'))

    # TODO: There's no reducer yet, so we can't actually collapse multiple
    # results into one results file.
    results = None
    for task_id, _ in tasks.iteritems():
      task_results_path = '%s/jobs/%s.result' % (
          cloud_config.Get().control_bucket_path, task_id)
      stat_result = cloud_helper.StatGCS(task_results_path)
      if stat_result is not None:
        logging.info(str(stat_result))
        tasks[task_id]['status'] = 'DONE'
        results = task_results_path

    if not results:
      taskqueue.add(
          url='/cloud_mapper/task',
          target=self._GetVersion(),
          countdown=1,
          params={'jobid': job.key.id(),
                  'type': 'check',
                  'tasks': json.dumps(tasks)})
      return

    logging.info("Finished all tasks.")

    job.status = 'COMPLETE'
    job.results = results
    job.put()

  def _RunMappers(self, job):
    # TODO(simonhatch): Figure out the optimal # of instances to spawn.
    num_instances = 1

    # Get all the traces to process
    traces = self._QueryForTraces(job.corpus, job.query)

    return self._DispatchTracesAndWaitForResult(job, traces, num_instances)

  def _CreateMapperJob(self, job):
    if job.status != 'QUEUED':
      return

    job.status = 'IN_PROGRESS'
    job.put()

    self._RunMappers(job)

  def post(self):
    self.response.headers['Content-Type'] = 'text/plain'

    jobid = self.request.get('jobid')
    job = job_info.JobInfo.get_by_id(jobid)
    if not job:
      return

    try:
      if self.request.get('type') == 'create':
        self._CreateMapperJob(job)
      elif self.request.get('type') == 'check':
        self._CheckOnResults(job)
    except Exception as e:
      job.status = 'ERROR'
      job.put()
      logging.exception('Failed job: %s' % e.message)


app = webapp2.WSGIApplication([('/cloud_mapper/task', TaskPage)])
