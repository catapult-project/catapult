# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Pinpoint FIFO Scheduler Handler

This HTTP handler is responsible for polling the state of the various FIFO
queues currently defined in the service, and running queued jobs as they are
ready. The scheduler enforces that there's only one currently runing job for any
configuration, and does not attempt to do any admission control nor load
shedding. Those features will be implemented in a dedicated scheduler service.
"""

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import webapp2

from dashboard.pinpoint.models import job as job_model
from dashboard.pinpoint.models import scheduler


class FifoScheduler(webapp2.RequestHandler):

  def get(self):
    configurations = scheduler.AllConfigurations()
    logging.info('Found %d FIFO Queues', len(configurations))
    for configuration in scheduler.AllConfigurations():
      logging.info('Processing queue \'%s\'', configuration)
      process_queue = True
      while process_queue:
        job_id, queue_status = scheduler.PickJob(configuration)

        if not job_id:
          logging.info('Empty queue.')
          process_queue = False
        else:
          process_queue = _ProcessJob(job_id, queue_status, configuration)


def _ProcessJob(job_id, queue_status, configuration):
  job = job_model.JobFromId(job_id)
  if not job:
    logging.error('Failed to load job with id: %s', job_id)
    scheduler.Remove(configuration, job_id)
    return False

  logging.info('Job "%s" status: "%s" queue: "%s"', job_id, job.status,
               configuration)

  if queue_status == 'Running':
    logging.debug('Job details: %r', job)
    if job.status in {'Failed', 'Completed'}:
      scheduler.Complete(job)
      return True  # Continue processing this queue.

  if queue_status == 'Queued':
    job.Start()

  return False
