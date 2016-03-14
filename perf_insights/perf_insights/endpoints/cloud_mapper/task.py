# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import datetime
import json
import logging
import math
import os
import urllib
import uuid
import webapp2

from google.appengine.api import taskqueue
from google.appengine.api import urlfetch
from perf_insights.endpoints.cloud_mapper import cloud_helper
from perf_insights.endpoints.cloud_mapper import job_info
from perf_insights import cloud_config

# If you modify this, you need to change the max_concurrent_requests in
# queue.yaml.
DEFAULT_TRACES_PER_INSTANCE = 4

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

    mapper_url = ''
    reducer_url = ''

    if job.reducer:
      reducer_url = '%s%s.reducer' % (bucket_path, job.key.id())
      reducer_text = job.reducer.encode('ascii', 'ignore')
      cloud_helper.WriteGCS(reducer_url, reducer_text)

    if job.mapper:
      mapper_url = '%s%s.mapper' % (bucket_path, job.key.id())
      mapper_text = job.mapper.encode('ascii', 'ignore')
      cloud_helper.WriteGCS(mapper_url, mapper_text)

      version = self._GetVersion()

      tasks = {}

      # Split the traces up into N buckets.
      logging.info('Splitting traces across %d instances.' % num_instances)
      for current_traces in _slice_it(traces, num_instances):
        logging.info('Submitting %d traces job.' % len(current_traces))
        task_id = str(uuid.uuid4())

        payload = {
            'revision': job.revision,
            'traces': json.dumps(current_traces),
            'result': '%s%s.result' % (bucket_path, task_id),
            'mapper': mapper_url,
            'mapper_function': job.mapper_function,
            'timeout': job.function_timeout,
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
      mapper_timeout = int(job.timeout - job.function_timeout)
      timeout = (
          datetime.datetime.now() + datetime.timedelta(
              seconds=mapper_timeout)).strftime(
                  '%Y-%m-%d %H:%M:%S')
      taskqueue.add(
          queue_name='default',
          url='/cloud_mapper/task',
          target=version,
          countdown=1,
          params={'jobid': job.key.id(),
                  'type': 'check_map_results',
                  'reducer': reducer_url,
                  'tasks': json.dumps(tasks),
                  'timeout': timeout})

  def _GetVersion(self):
    version = os.environ['CURRENT_VERSION_ID'].split('.')[0]
    if cloud_config._is_devserver():
      version = taskqueue.DEFAULT_APP_VERSION
    return version

  def _CheckOnMapResults(self, job):
    if job.status != 'IN_PROGRESS':
      return

    tasks = json.loads(self.request.get('tasks'))
    reducer_url = self.request.get('reducer')
    reducer_function = job.reducer_function
    revision = job.revision
    timeout = datetime.datetime.strptime(
        self.request.get('timeout'), '%Y-%m-%d %H:%M:%S')

    # TODO: There's no reducer yet, so we can't actually collapse multiple
    # results into one results file.
    mappers_done = True
    for task_id, task_values in tasks.iteritems():
      if task_values['status'] == 'DONE':
        continue
      task_results_path = '%s/jobs/%s.result' % (
          cloud_config.Get().control_bucket_path, task_id)
      stat_result = cloud_helper.StatGCS(task_results_path)
      if stat_result is not None:
        logging.info(str(stat_result))
        tasks[task_id]['status'] = 'DONE'
      else:
        mappers_done = False

    logging.info("Tasks: %s" % str(tasks))

    if not mappers_done and datetime.datetime.now() < timeout:
      taskqueue.add(
          url='/cloud_mapper/task',
          target=self._GetVersion(),
          countdown=1,
          params={'jobid': job.key.id(),
                  'type': 'check_map_results',
                  'reducer': reducer_url,
                  'tasks': json.dumps(tasks),
                  'timeout': self.request.get('timeout')})
      return

    # Clear out any leftover tasks in case we just hit the timeout.
    self._CancelTasks(tasks)

    map_results = []
    for task_id, _ in tasks.iteritems():
      if tasks[task_id]['status'] != 'DONE':
        continue
      task_results_path = '%s/jobs/%s.result' % (
          cloud_config.Get().control_bucket_path, task_id)
      map_results.append(task_results_path)

    # We'll only do 1 reduce job for now, maybe shard it better later
    logging.info("Kicking off reduce.")
    task_id = str(uuid.uuid4())
    payload = {
        'revision': revision,
        'traces': json.dumps(map_results),
        'result': '%s/jobs/%s.result' % (
            cloud_config.Get().control_bucket_path, task_id),
        'reducer': reducer_url,
        'reducer_function': reducer_function,
        'timeout': job.function_timeout,
    }
    taskqueue.add(
        queue_name='mapper-queue',
        url='/cloud_worker/task',
        target=self._GetVersion(),
        name=task_id,
        params=payload)

    tasks = {}
    tasks[task_id] = {'status': 'IN_PROGRESS'}

    job.running_tasks = [task_id for task_id, _ in tasks.iteritems()]
    job.put()

    reduce_tasks = {}
    reduce_tasks[task_id] = {'status': 'IN_PROGRESS'}

    # On production servers, we could just sit and wait for the results, but
    # dev_server is single threaded and won't run any other tasks until the
    # current one is finished. We'll just do the easy thing for now and
    # queue a task to check for the result.
    reducer_timeout = int(job.function_timeout)
    timeout = (
        datetime.datetime.now() + datetime.timedelta(
            seconds=reducer_timeout)).strftime(
                '%Y-%m-%d %H:%M:%S')
    taskqueue.add(
        queue_name='default',
        url='/cloud_mapper/task',
        target=self._GetVersion(),
        countdown=1,
        params={'jobid': job.key.id(),
                'type': 'check_reduce_results',
                'tasks': json.dumps(reduce_tasks),
                'timeout': timeout})

  def _CancelTasks(self, tasks):
    task_names = [task_id for task_id, _ in tasks.iteritems()]
    taskqueue.Queue('mapper-queue').delete_tasks_by_name(task_names)

  def _CheckOnReduceResults(self, job):
    if job.status != 'IN_PROGRESS':
      return

    tasks = json.loads(self.request.get('tasks'))

    # TODO: There's really only one reducer job at the moment
    results = None
    for task_id, _ in tasks.iteritems():
      task_results_path = '%s/jobs/%s.result' % (
          cloud_config.Get().control_bucket_path, task_id)
      stat_result = cloud_helper.StatGCS(task_results_path)
      if stat_result is not None:
        tasks[task_id]['status'] = 'DONE'
        results = task_results_path

    logging.info("Reduce results: %s" % str(tasks))

    if not results:
      timeout = datetime.datetime.strptime(
          self.request.get('timeout'), '%Y-%m-%d %H:%M:%S')
      if datetime.datetime.now() > timeout:
        self._CancelTasks(tasks)
        job.status = 'ERROR'
        job.put()
        logging.error('Task timed out waiting for results.')
        return
      taskqueue.add(
          url='/cloud_mapper/task',
          target=self._GetVersion(),
          countdown=1,
          params={'jobid': job.key.id(),
                  'type': 'check_reduce_results',
                  'tasks': json.dumps(tasks),
                  'timeout': self.request.get('timeout')})
      return

    logging.info("Finished all tasks.")

    job.status = 'COMPLETE'
    job.results = results
    job.put()

  def _CalculateNumInstancesNeeded(self, num_traces):
    return int(math.ceil(float(num_traces) / DEFAULT_TRACES_PER_INSTANCE))

  def _RunMappers(self, job):
    # Get all the traces to process
    traces = self._QueryForTraces(job.corpus, job.query)

    # We can probably be smarter about this down the road, maybe breaking
    # this into many smaller tasks and allowing each instance to run
    # several tasks at once. For now we'll just break it into a few big ones.
    num_instances = self._CalculateNumInstancesNeeded(len(traces))

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
      elif self.request.get('type') == 'check_map_results':
        self._CheckOnMapResults(job)
      elif self.request.get('type') == 'check_reduce_results':
        self._CheckOnReduceResults(job)
    except Exception as e:
      job.status = 'ERROR'
      job.put()
      logging.exception('Failed job: %s' % e.message)


app = webapp2.WSGIApplication([('/cloud_mapper/task', TaskPage)])
