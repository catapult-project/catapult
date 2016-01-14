# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import Queue as queue

import json
import logging
import os
import shutil
import subprocess
import tempfile
import threading
import traceback
import webapp2

from perf_insights import cloud_config
from perf_insights.endpoints.cloud_mapper import cloud_helper


_DEFAULT_PARALLEL_DOWNLOADS = 16


class EnvVarModifier(object):

  def __init__(self, **kwargs):
    self._vars = {}
    self._kwargs = kwargs

  def __enter__(self):
    for k, v in self._kwargs.iteritems():
      self._vars[k] = os.environ.get(k)
      os.environ[k] = v
    return self

  def __exit__(self, *_):
    for k, v in self._vars.iteritems():
      os.environ[k] = v


def _is_devserver():
  server_software = os.environ.get('SERVER_SOFTWARE', '')
  return server_software and server_software.startswith('Development')


def _DownloadTraces(traces):
  work_queue = queue.Queue()
  for t in traces:
    work_queue.put(t)

  temp_directory = tempfile.mkdtemp()

  def _WorkLoop():
    while not work_queue.empty():
      trace_url = work_queue.get()
      local_name = trace_url.split('/')[-1]
      try:
        with open(os.path.join(temp_directory, local_name), 'w') as dst:
          with EnvVarModifier(SERVER_SOFTWARE='') as _:
            cloud_helper.ReadGCSToFile(trace_url, dst)
      except Exception as e:
        logging.info("Failed to copy: %s" % e)
      work_queue.task_done()

  for _ in xrange(_DEFAULT_PARALLEL_DOWNLOADS):
    t = threading.Thread(target=_WorkLoop)
    t.setDaemon(True)
    t.start()
  work_queue.join()

  return temp_directory


class TaskPage(webapp2.RequestHandler):

  def post(self):
    os.putenv('PI_CLOUD_WORKER', '1')
    try:
      traces = json.loads(self.request.get('traces'))
      mapper = self.request.get('mapper')
      map_function = self.request.get('mapper_function')
      revision = self.request.get('revision')
      result_path = self.request.get('result')

      config = cloud_config.Get()

      if not _is_devserver():
        subprocess.call(
            ['git', 'pull'], cwd=config.catapult_path)
        subprocess.call(
            ['git', 'checkout', revision],
            cwd=config.catapult_path)
        job_path = os.path.join(
            config.catapult_path, 'perf_insights', 'bin', 'map_traces')
        cwd = config.catapult_path
      else:
        job_path = os.path.join('perf_insights', 'bin', 'map_traces')
        cwd = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '../../../..'))

      # Download all the traces
      temp_directory = _DownloadTraces(traces)

      # Download the mapper
      map_file_handle, map_file_name = tempfile.mkstemp()
      with open(map_file_name, 'w') as f:
        f.write(cloud_helper.ReadGCS(mapper))

      # Output goes here.
      output_handle, output_name = tempfile.mkstemp()

      try:
        map_handle = '%s:%s' % (map_file_name, map_function)
        args = [job_path, '--jobs=-1', '--corpus=local-directory', map_handle,
            '--trace_directory', temp_directory, '--output-file', output_name]
        logging.info("Executing map job: %s" % args)

        map_job = subprocess.Popen(args,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   cwd=cwd)
        stdout, stderr = map_job.communicate()

        logging.info('stdout:\n' + stdout)
        logging.info('stderr:\n' + stderr)

        with open(output_name, 'r') as f:
          cloud_helper.WriteGCS(result_path, f.read())
      finally:
        os.close(output_handle)
        os.unlink(output_name)
        os.close(map_file_handle)
        os.unlink(map_file_name)
        shutil.rmtree(temp_directory)
    except Exception:
      logging.info(traceback.format_exc())


app = webapp2.WSGIApplication([('/cloud_worker/task', TaskPage)])
