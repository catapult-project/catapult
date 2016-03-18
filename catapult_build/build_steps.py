# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import json
import os
import sys

# This is the list of tests to run. It is a dictionary with the following
# fields:
#
# name (required): The name of the step, to show on the buildbot status page.
# path (required): The path to the executable which runs the tests.
# additional_args (optional): An array of optional arguments.
# uses_app_engine_sdk (optional): True if app engine SDK must be in PYTHONPATH.
# uses_sandbox_env (optional): True if CHROME_DEVEL_SANDBOX must be in
#   environment.
# disabled (optional): List of platforms the test is disabled on. May contain
#   'win', 'mac', or 'linux'.
# outputs_presentation_json (optional): If True, pass in --presentation-json
#   argument to the test executable to allow it to update the buildbot status
#   page. More details here:
# github.com/luci/recipes-py/blob/master/recipe_modules/generator_script/api.py
_CATAPULT_TESTS = [
    {
        'name': 'Build Python Tests',
        'path': 'catapult_build/bin/run_py_tests',
    },
    {
        'name': 'Catapult Base Tests',
        'path': 'catapult_base/bin/run_tests',
    },
    {
        'name': 'Dashboard Dev Server Tests Canary',
        'path': 'dashboard/bin/run_dev_server_tests',
        'additional_args': [
            '--no-install-hooks',
            '--no-use-local-chrome',
            '--channel=canary'
        ],
        # https://github.com/catapult-project/catapult/issues/2138
        'disabled': ['linux', 'mac', 'win'],
        'outputs_presentation_json': True,
    },
    {
        'name': 'Dashboard Dev Server Tests Stable',
        'path': 'dashboard/bin/run_dev_server_tests',
        'additional_args': [
            '--no-install-hooks',
            '--no-use-local-chrome',
            '--channel=stable',
        ],
        'outputs_presentation_json': True,
    },
    {
        'name': 'Dashboard Python Tests',
        'path': 'dashboard/bin/run_py_tests',
        'additional_args': ['--no-install-hooks'],
        'uses_app_engine_sdk': True,
    },
    {
        'name': 'Dependency Manager Tests',
        'path': 'dependency_manager/bin/run_tests',
    },
    {
        'name': 'Devil Python Tests',
        'path': 'devil/bin/run_py_tests',
        'disabled': ['mac', 'win'],
    },
    {
        'name': 'Perf Insights Dev Server Tests Canary',
        'path': 'perf_insights/bin/run_dev_server_tests',
        'additional_args': [
            '--no-install-hooks',
            '--no-use-local-chrome',
            '--channel=canary'
        ],
        # https://github.com/catapult-project/catapult/issues/2138
        'disabled': ['linux', 'mac', 'win'],
        'outputs_presentation_json': True,
    },
    {
        'name': 'Perf Insights Dev Server Tests Stable',
        'path': 'perf_insights/bin/run_dev_server_tests',
        'additional_args': [
            '--no-install-hooks',
            '--no-use-local-chrome',
            '--channel=stable',
        ],
        'uses_sandbox_env': True,
        'outputs_presentation_json': True,
    },
    {
        'name': 'Perf Insights Python Tests',
        'path': 'perf_insights/bin/run_py_tests',
        'additional_args': ['--no-install-hooks'],
    },
    {
        'name': 'Perf VINN Insights Tests',
        'path': 'perf_insights/bin/run_vinn_tests',
    },
    {
        'name': 'Py-vulcanize Tests',
        'path': 'third_party/py_vulcanize/bin/run_py_tests',
        'additional_args': ['--no-install-hooks'],
    },
    {
        'name': 'Systrace Tests',
        'path': 'systrace/bin/run_tests',
    },
    {
        'name': 'Telemetry Tests with Stable Browser',
        'path': 'telemetry/bin/run_tests',
        'additional_args': [
            '--browser=reference',
            '--start-xvfb'
        ],
        'uses_sandbox_env': True,
    },
    {
        'name': 'Tracing Dev Server Tests Canary',
        'path': 'tracing/bin/run_dev_server_tests',
        'additional_args': [
            '--no-install-hooks',
            '--no-use-local-chrome',
            '--channel=canary'
        ],
        # Test failing on Windows:
        # https://github.com/catapult-project/catapult/issues/1816
        # Tests failing on all platform:
        # https://github.com/catapult-project/catapult/issues/2138
        'disabled': ['win', 'linux', 'mac'],
        'outputs_presentation_json': True,
    },
    {
        'name': 'Tracing Dev Server Tests Stable',
        'path': 'tracing/bin/run_dev_server_tests',
        'additional_args': [
            '--no-install-hooks',
            '--no-use-local-chrome',
            '--channel=stable',
        ],
        'outputs_presentation_json': True,
    },
    {
        'name': 'Tracing D8 Tests',
        'path': 'tracing/bin/run_vinn_tests',
    },
    {
        'name': 'Tracing Python Tests',
        'path': 'tracing/bin/run_py_tests',
        'additional_args': ['--no-install-hooks'],
    },
    {
        'name': 'Vinn Tests',
        'path': 'third_party/vinn/run_test',
    },
]


def main(args=None):
  """Send list of test to run to recipes generator_script.

  See documentation at:
  github.com/luci/recipes-py/blob/master/recipe_modules/generator_script/api.py
  """
  parser = argparse.ArgumentParser(description='Run catapult tests.')
  parser.add_argument('--api-path-checkout', help='Path to catapult checkout')
  parser.add_argument('--app-engine-sdk-pythonpath',
                      help='PYTHONPATH to include app engine SDK path')
  parser.add_argument('--platform',
                      help='Platform name (linux, mac, or win)')
  parser.add_argument('--output-json', help='Output for buildbot status page')
  args = parser.parse_args(args)

  steps = []
  for test in _CATAPULT_TESTS:
    if args.platform in test.get('disabled', []):
      continue
    step = {
        'name': test['name'],
        'env': {}
    }
    step['cmd'] = ['python', os.path.join(args.api_path_checkout, test['path'])]
    if test.get('additional_args'):
      step['cmd'] += test['additional_args']
    if test.get('uses_app_engine_sdk'):
      step['env']['PYTHONPATH'] = args.app_engine_sdk_pythonpath
    if test.get('uses_sandbox_env'):
      step['env']['CHROME_DEVEL_SANDBOX'] = '/opt/chromium/chrome_sandbox'
    if test.get('outputs_presentation_json'):
      step['outputs_presentation_json'] = True
    steps.append(step)
  with open(args.output_json, 'w') as outfile:
    json.dump(steps, outfile)


if __name__ == '__main__':
  main(sys.argv[1:])
