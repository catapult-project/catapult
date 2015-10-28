#!/usr/bin/env python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import csv
import logging
import os
import subprocess
import sys
import time

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from telemetry.core import platform


MONITORING_DURATION_SECONDS = 60 * 60
SAMPLE_INTERVAL_SECONDS = 10
RESULTS_FILE_NAME = 'service_benchmark_results.csv'
METRIC_NAMES = ['Power (W)', 'Temperature (C)']
FIELD_NAMES = ['label'] + METRIC_NAMES
SERVICES = (
    'Adobe Acrobat Update Service',
    'DSM SA Connection Service',
    'DSM SA Data Manager',
    'DSM SA Event Manager',
    'DSM SA Shared Services',
    'Intel(R) HD Graphics Control Panel Service',
    'LEMSS Agent',
    'Lumension Patch Module',
    #'NSClient++ (x64)',
    'Puppet Agent',
    'SQL Server VSS Writer',
    'Windows Firewall',
    'Windows Update',
)


def MonitorAndRecordPower(label):
  logging.debug('Monitoring %s for %d seconds...', label, MONITORING_DURATION_SECONDS)

  results = []
  for _ in xrange(int(MONITORING_DURATION_SECONDS / SAMPLE_INTERVAL_SECONDS)):
    platform.GetHostPlatform().StartMonitoringPower(None)
    time.sleep(SAMPLE_INTERVAL_SECONDS)
    result = platform.GetHostPlatform().StopMonitoringPower()

    result = {
        'label': label,
        'Power (W)': result['energy_consumption_mwh'] * 3.6 / SAMPLE_INTERVAL_SECONDS,
        'Temperature (C)': result['component_utilization']['whole_package']['average_temperature_c'],
    }
    results.append(result)

  with open(RESULTS_FILE_NAME, 'a') as results_file:
    for result in results:
      csv.DictWriter(results_file, fieldnames=FIELD_NAMES).writerow(result)


def DisableService(service):
  logging.debug('Stopping %s.', service)
  subprocess.check_call(('net', 'stop', service), stdout=subprocess.PIPE)


def EnableService(service):
  logging.debug('Starting %s.', service)
  subprocess.check_call(('net', 'start', service), stdout=subprocess.PIPE)


class PauseServices(object):
  def __init__(self, services):
    self._services = services
    self._disabled_services = []

  def __enter__(self):
    for service in self._services:
      try:
        DisableService(service)
        self._disabled_services.append(service)
      except subprocess.CalledProcessError:
        logging.info('Failed to stop %s.' % service)

  def __exit__(self, _, __, ___):
    for service in self._disabled_services:
      try:
        EnableService(service)
      except subprocess.CalledProcessError:
        logging.info('Failed to start %s.' % service)
    self._disabled_services = []


def ReformatResults():
  results = {}
  for metric in METRIC_NAMES:
    results[metric] = {}
  with open(RESULTS_FILE_NAME, 'r') as results_file:
    reader = csv.DictReader(results_file)
    for row in reader:
      for metric in METRIC_NAMES:
        if row['label'] not in results[metric]:
          results[metric][row['label']] = []
        results[metric][row['label']].append(row[metric])

  for metric in METRIC_NAMES:
    root, ext = os.path.splitext(RESULTS_FILE_NAME)
    metric_results_file_name = '%s %s%s' % (root, metric, ext)
    with open(metric_results_file_name, 'w') as metric_results_file:
      labels = results[metric].keys()
      writer = csv.DictWriter(metric_results_file, fieldnames=labels)
      writer.writeheader()

      data_point_count = max(map(len, results[metric].itervalues()))
      for i in xrange(data_point_count):
        writer.writerow({label: results[metric][label][i] for label in labels})


def SetUp():
  logging.getLogger().setLevel(logging.INFO)

  if not platform.GetHostPlatform().CanMonitorPower():
    print >> sys.stderr, "Can't monitor power."
    sys.exit(1)

  with open(RESULTS_FILE_NAME, 'w') as results_file:
    csv.DictWriter(results_file, fieldnames=FIELD_NAMES).writeheader()


def main():
  SetUp()

  logging.info('Testing %d services.' % len(SERVICES))

  logging.info('Testing with services enabled for %d seconds.',
               MONITORING_DURATION_SECONDS)
  MonitorAndRecordPower('default')

  with PauseServices(SERVICES):
    logging.info('Testing with services disabled for %d seconds.',
                 MONITORING_DURATION_SECONDS)
    MonitorAndRecordPower('control')

    for i, service in enumerate(SERVICES):
      logging.info('Testing %s for %d seconds. (%d/%d)', service,
                   MONITORING_DURATION_SECONDS, i + 1, len(SERVICES))
      EnableService(service)
      MonitorAndRecordPower(service)
      DisableService(service)

  ReformatResults()


if __name__ == '__main__':
  main()
