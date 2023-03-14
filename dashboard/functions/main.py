# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import functions_framework
from flask import jsonify

from common import dashboard_service, pinpoint_service, cabe_service


@functions_framework.http
def StartPinpointJob(request):
  """Start a Pinpoint job from an input anomaly.

  Args:
    anomaly: a map with the following attributes:
      benchmark (e.g. "speedometer2")
      story (e.g. "Speedometer2")
      start_git_hash (a valid git hash)
      base_git_hash (a valid git hash)
      bot_name (e.g. "mac-m1_mini_2020-perf")
      target (e.g. "performance_test_suite")
  Returns:
    Job ID of started Pinpoint Job.
  """
  request_json = request.get_json(silent=True)

  print('Original params: %s' % request_json)
  anomaly = request_json.get('anomaly')

  bot_name = anomaly.get('bot_name')
  benchmark_name = anomaly.get('benchmark')

  name = 'Regression Verification Try job on %s/%s' % (bot_name, benchmark_name)

  pinpoint_params = {
      'benchmark': benchmark_name,
      'story': anomaly.get('story'),
      'base_git_hash': anomaly.get('start_git_hash'),
      'end_git_hash': anomaly.get('end_git_hash'),
      'configuration': bot_name,
      'target': anomaly.get('target'),
      'name': name,
      'comparison_mode': 'try',
      'try': 'on',
      'project': anomaly.get('project', 'chromium')
  }

  print('Starting job with params: %s' % pinpoint_params)

  results = pinpoint_service.NewJob(pinpoint_params)

  print('Starting job response: %s' % results)

  return jsonify({'job_id': results.get('jobId')})


@functions_framework.http
def PollPinpointJob(request):
  """Poll Pinpoint service for status of a job.

  Args:
    job_id: a valid Pinpoint job id.
  Returns:
    Status from {"Completed", "Queued", "Cancelled", "Failed", "Running"}
  """
  request_json = request.get_json(silent=True)

  print('Original params: %s' % request_json)

  job_id = request_json.get('job_id')

  print("Getting Job: %s" % job_id)

  results = pinpoint_service.GetJob(job_id)

  print('Getting job response: %s' % results)

  return jsonify({'status': results.get('status')})


@functions_framework.http
def GetCabeAnalysis(request):
  """Call CABE Analysis API.

  Get a CABE Analysis object from a Pinpoint Job. It'll return a list of
  statistics for multiple workloads. anomaly.chart input will specify which
  workload we're interested in.

  Args:
    job_id: a valid Completed Pinpoint job id.
    anomaly: an map with the following attribute:
      chart: workload (e.g. "AngularJS-TodoMVC")
  Returns:
    A statistic map with upper and lower confidence intervals.
  """

  request_json = request.get_json(silent=True)

  print('Original params: %s' % request_json)

  measurement = request_json.get('anomaly').get('chart')
  job_id = request_json.get('job_id')

  print("Getting CABE Analysis from Job: %s" % job_id)
  results = cabe_service.GetAnalysis(job_id)
  print("CABE Analysis response: %s" % results)

  statistic = None

  for result in results:
    if measurement == result['experiment_spec']['analysis']['benchmark'][
        'workload']:
      statistic = result['statistic']
  print("get_cabe_analysis statistic: %s" % statistic)

  return jsonify({'statistic': statistic})


@functions_framework.http
def RegressionDetection(request):
  """Determine whether an anomaly is statistically significant.

  Given upper and lower confidence intervals, we currently use a simple
  formula to determine whether an anomaly is significant. If upper and lower
  are both greater -5%, then we consider the anomaly a verified regression.

  Args:
    statistic: map with upper and lower confidence interval values.
  Returns:
    A decision on whether an anomaly is statistically significant.
  """
  request_json = request.get_json(silent=True)

  print('Original params: %s' % request_json)

  statistic = request_json.get('statistic')

  ci_lower = statistic.get('lower')
  ci_upper = statistic.get('upper')

  decision = False

  if ci_lower >= -5 and ci_upper >= -5:
    decision = True

  return jsonify({'decision': decision})


@functions_framework.http
def HandlerCallback(request):
  """Call external service API with verification results.

  Args:
    anomaly: verified anomaly.
    error: any error that occurred in the verification workflow.
    decision: True or False, determines whether anomaly is significant.
    statistic: analysis results of anomaly.
    mode: String that helps determine which API to call.
    args: any extra arguments that might be useful to the external API.
  """
  request_json = request.get_json(silent=True)

  print('Original params: %s' % request_json)

  mode = request_json.get('mode')
  args = request_json.get('args')

  verification = {
      'anomaly': request_json.get('anomaly'),
      'error': request_json.get('error'),
      'decision': request_json.get('decision'),
      'statistic': request_json.get('statistic'),
  }

  resp = None

  if mode == 'alert_group':
    req = {
        'verification': verification,
        'group': args.get('group_key'),
        'update': args.get('update'),
    }
    resp = dashboard_service.VerifiedAlertGroup(req)

  return jsonify({'response': resp})
