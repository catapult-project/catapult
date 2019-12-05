# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import webapp2

from dashboard.pinpoint.models import job as job_module
from dashboard.pinpoint.models import task as task_module
from dashboard.pinpoint.models import event as event_module
from dashboard.pinpoint.models.tasks import evaluator


class Run(webapp2.RequestHandler):
  """Handler that runs a Pinpoint job."""

  def post(self, job_id):
    job = job_module.JobFromId(job_id)
    if job.use_execution_engine:
      event = event_module.Event(type='initiate', target_task=None, payload={})
      logging.info('Execution Engine: Evaluating initiate event.')
      task_module.Evaluate(job, event, evaluator.ExecutionEngine(job))
      logging.info('Execution Engine: Evaluation done.')
    else:
      job.Run()
