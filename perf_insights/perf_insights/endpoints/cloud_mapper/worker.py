# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import Queue as queue

import datetime
import json
import logging
import os
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import traceback
import webapp2

from perf_insights import cloud_config
from perf_insights.endpoints.cloud_mapper import cloud_helper


_DEFAULT_PARALLEL_DOWNLOADS = 64
_DEFAULT_RETRIES = 3


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
      for _ in xrange(_DEFAULT_RETRIES):
        try:
          logging.info('downloading: %s' % trace_url)
          # TODO: This is dumb, but we have local vs actual cloud storage.
          # Fix this.
          if '.gz' in local_name:
            with open(os.path.join(temp_directory, local_name), 'w') as dst:
              cloud_helper.ReadGCSToFile(trace_url, dst)
          else:
            with open(os.path.join(temp_directory, local_name), 'w') as dst:
              cloud_helper.ReadGCSToFile(trace_url, dst)
          break
        except Exception as e:
          logging.info("Failed to copy: %s" % e)
        time.sleep(0.5)
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
      reducer = self.request.get('reducer')
      reducer_function = self.request.get('reducer_function')
      revision = self.request.get('revision')
      result_path = self.request.get('result')
      timeout = self.request.get('timeout')
      if timeout:
        timeout = int(timeout)

      config = cloud_config.Get()

      if not _is_devserver():
        logging.info("Updating catapult checkout to: %s" % revision)
        subprocess.call(
            ['git', 'checkout', revision],
            cwd=config.catapult_path)
        job_path = os.path.join(
            config.catapult_path, 'perf_insights', 'bin',
            'gce_instance_map_job')
        cwd = config.catapult_path
      else:
        logging.info("DevServer: Ignoring update step.")
        job_path = os.path.join('perf_insights', 'bin', 'gce_instance_map_job')
        cwd = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '../../../..'))

      # Download all the traces
      temp_directory = _DownloadTraces(traces)

      # Output goes here.
      output_handle, output_name = tempfile.mkstemp()

      try:
        args = [job_path, '--corpus=local-directory',
            '--trace_directory', temp_directory, '--output-file', output_name]
        if mapper:
          # Download the mapper
          _, map_file_name = tempfile.mkstemp()
          with open(map_file_name, 'w') as f:
            f.write(cloud_helper.ReadGCS(mapper))
          map_handle = '%s:%s' % (map_file_name, map_function)
          args.extend(['--map_function_handle', map_handle])
        if reducer:
          # Download the reducer
          _, reducer_file_name = tempfile.mkstemp()
          with open(reducer_file_name, 'w') as f:
            f.write(cloud_helper.ReadGCS(reducer))
          reducer_handle = '%s:%s' % (reducer_file_name, reducer_function)
          args.extend(['--reduce_function_handle', reducer_handle])
        logging.info("Executing map job: %s" % ' '.join(args))

        map_job = subprocess.Popen(args,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   cwd=cwd,
                                   preexec_fn=os.setsid)
        start_time = datetime.datetime.now()
        while datetime.datetime.now() - start_time < datetime.timedelta(
            seconds=timeout):
          time.sleep(1)
          if map_job.poll():
            break

        if map_job.poll() is None:
          logging.warning('Job timed out, terminating.')
          # TODO: Kill child processes.
          os.killpg(os.getpgid(map_job.pid), signal.SIGTERM)

        stdout = ''
        stderr = ''
        if map_job.stdout:
          stdout = map_job.stdout.read()
        if map_job.stderr:
          stderr = map_job.stderr.read()

        logging.info('stdout:\n' + stdout)
        logging.info('stderr:\n' + stderr)

        with open(output_name, 'r') as f:
          logging.info('Writing result to: %s' % result_path)
          cloud_helper.WriteGCS(result_path, f.read())
      finally:
        os.close(output_handle)
        os.unlink(output_name)
        shutil.rmtree(temp_directory)
    except Exception:
      logging.info(traceback.format_exc())


app = webapp2.WSGIApplication([('/cloud_worker/task', TaskPage)])
