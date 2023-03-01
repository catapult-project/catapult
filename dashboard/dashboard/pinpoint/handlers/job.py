# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json

from flask import make_response, request

from dashboard.common import cloud_metric
from dashboard.pinpoint.models import job as job_module


@cloud_metric.APIMetric("pinpoint", "/api/job")
def JobHandlerGet(job_id):
  try:
    job = job_module.JobFromId(job_id)
  except ValueError:
    return make_response(
        json.dumps({'error': 'Invalid job id: %s' % job_id}), 400)

  if not job:
    return make_response(
        json.dumps({'error': 'Unknown job id: %s' % job_id}), 404)

  opts = request.args.getlist('o')
  return make_response(json.dumps(job.AsDict(opts)))
