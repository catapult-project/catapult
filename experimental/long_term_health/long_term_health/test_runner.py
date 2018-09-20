# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Helper function to run the benchmark.

If there is problem, try `gclient sync` to ensure everything is the latest.
"""
import ast
import contextlib
import json
import os
import shutil
import subprocess
import tempfile
import time

from long_term_health import utils
from long_term_health.apk_finder import ChromeVersion


SWARMING_URL = 'https://chrome-swarming.appspot.com'
ISOLATE_SERVER_URL = 'https://chrome-isolated.appspot.com'

CATAPULT_ROOT = os.path.normpath(os.path.join(utils.APP_ROOT, '..', '..'))
CHROMIUM_ROOT = os.path.normpath(os.path.join(CATAPULT_ROOT, '..', '..'))
MB = os.path.join(CHROMIUM_ROOT, 'tools', 'mb', 'mb.py')
SWARMING_CLIENT = os.path.join(CHROMIUM_ROOT, 'tools', 'swarming_client')
ISOLATE_SERVER_SCRIPT = os.path.join(SWARMING_CLIENT, 'isolateserver.py')
ISOLATE_SCRIPT = os.path.join(SWARMING_CLIENT, 'isolate.py')
SWARMING_SCRIPT = os.path.join(SWARMING_CLIENT, 'swarming.py')
PATH_TO_APKS = os.path.join(CHROMIUM_ROOT, 'tools', 'perf', 'swarming_apk')
TEST_BUILD_GN = os.path.join(CHROMIUM_ROOT, 'chrome', 'test', 'BUILD.gn')
GN_ISOLATE_MAP = os.path.join(
    CHROMIUM_ROOT, 'testing', 'buildbot', 'gn_isolate_map.pyl')


RESULT_FILE_NAME = 'perf_results.json'


def FindFilesByExtension(dir_path, extension):
  files = []
  for name in os.listdir(dir_path):
    if name.endswith(extension):
      files.append(os.path.join(dir_path, name))
  return files


@contextlib.contextmanager
def RestoreFileContents(file_paths):
  """Context Manager to restore the file contents after modifications.

  Args:
    file_paths(list of strings): a list of paths to the files that you want to
      keep unmodified

  Yields:
    To allow for modification of the file content.
  """
  temp_dir = tempfile.mkdtemp()
  try:
    for file_path in file_paths:
      shutil.copyfile(
          file_path, os.path.join(temp_dir, os.path.basename(file_path)))
    yield
    for file_path in file_paths:
      shutil.copyfile(
          os.path.join(temp_dir, os.path.basename(file_path)), file_path)
  finally:
    shutil.rmtree(temp_dir)


def AddNewTargetToBUILD():
  """Add a new target to the `chrome/test/BUILD.gn`."""
  with open(TEST_BUILD_GN, 'a') as build_gn:
    build_gn.write(
        '''
# Difference between this and performance_test_suite is that this runs a devil
# script before the build, to remove the system chrome. See
# //testing/buildbot/gn_isolate_map.pyl
group("performance_system_chrome_test_suite") {
  testonly = true
  deps = [
    "//chrome/test:performance_test_suite",
  ]
}
        '''
    )
    build_gn.write('\n')  # seems like causing some strange indent problem...


def AddTargetToIsolateMap():
  """Add a ninja target to the corresponding gn label."""
  with open(GN_ISOLATE_MAP, 'r') as content:
    isolate_map_content = ast.literal_eval(content.read())

  isolate_map_content['performance_system_chrome_test_suite'] = {
      'label': '//chrome/test:performance_system_chrome_test_suite',
      'type': 'script',
      'script':
          '//third_party/catapult/devil/devil/android/tools/system_app.py',
      'args': [
          'remove',
          '--package',
          'com.android.chrome',
          '-v',
          '--',
          '../../testing/scripts/run_performance_tests.py',
          '../../tools/perf/run_benchmark',
      ],
  }

  with open(GN_ISOLATE_MAP, 'w') as isolate_map_file:
    isolate_map_file.write(repr(isolate_map_content))


def IncludeAPKInIsolate(apk_path):
  apk_name = os.path.basename(apk_path)
  if not os.path.isdir(PATH_TO_APKS):
    os.mkdir(PATH_TO_APKS)
  shutil.copyfile(apk_path, os.path.join(PATH_TO_APKS, apk_name))
  # relative path to be used when starting swarming job
  return os.path.join('..', '..', 'tools', 'perf', 'swarming_apk', apk_name)


def GenerateIsolate(out_dir_path, target_name):
  """Generate the isolate for the given target.

  This function will try to fetch the latest benchmark DEPs and remove sha1 file
  before generating the isolate.

  Args:
    out_dir_path(string): the directory that you want the isolate to be in
    target_name(string): the name of the target
  """
  # TODO(wangge): need to make it work even if there is no `out/Debug`
  subprocess.check_call(
      ['python', os.path.join(
          CHROMIUM_ROOT, 'tools', 'perf', 'fetch_benchmark_deps.py'),
       'system_health.memory_mobile'])
  hash_files = FindFilesByExtension(os.path.join(
      CHROMIUM_ROOT, 'tools', 'perf', 'page_sets', 'data'), '.sha1')
  with RestoreFileContents([TEST_BUILD_GN, GN_ISOLATE_MAP] + hash_files):
    AddNewTargetToBUILD()
    AddTargetToIsolateMap()
    # remove the hash files to allow the swarming bot to run the benchmark,
    # otherwise the Telemetry will attempt to download the WPR recordings again.
    for hash_file in hash_files:
      os.remove(hash_file)
    subprocess.check_call([MB, 'isolate', out_dir_path, target_name])


def UploadIsolate(isolated_path):
  """Returns the input isolate hash."""
  return subprocess.check_output(
      [ISOLATE_SCRIPT, 'archive', '-I', ISOLATE_SERVER_URL,
       '-s', isolated_path]).split(' ')[0]


def TriggerSwarmingJob(isolate_hash, isolated_apk_path):
  """Function to trigger the swarming job.

  Args:
    isolate_hash(string): the isolate hash given by the isolate server
    isolated_apk_path(string): the *relative* path to the APK in the isolate

  Returns:
    string: swarming job task hash
  """
  # set the swarming task attribute
  swarming_trigger_options = [
      SWARMING_SCRIPT, 'trigger',
      # select which swarming server to use
      '--swarming', SWARMING_URL,
      # select which isolate server to use
      '--isolate-server', ISOLATE_SERVER_URL,
      '--priority', '25',
      # set the task name
      '--task-name', 'long_term_health_task',
      # the isolate hash that is to be used
      '--isolated', isolate_hash,
  ]
  # select the bot criteria
  bot_dimension_options = [
      '--dimension', 'pool', 'chrome.tests.pinpoint',
      '--dimension', 'os', 'Android',
      '--dimension', 'device_os_flavor', 'google',
  ]
  # options provided to the `run_benchmark` script
  run_benchmark_options = [
      'system_health.memory_mobile',
      '--pageset-repeat', '1',
      '--compatibility-mode=no-field-trials',
      '--compatibility-mode=ignore-certificate-errors',
      '--compatibility-mode=legacy-command-line-path',
      '--compatibility-mode=gpu-benchmarking-fallbacks',
      '--browser', 'exact', '--device', 'android',
      '--browser-executable', isolated_apk_path,
      '--upload-results', '--output-format', 'histograms',
      '--results-label', 'Test Run 1',
  ]
  output_options = [
      '--isolated-script-test-output', '${ISOLATED_OUTDIR}/output.json',
      '--isolated-script-test-perf-output',
      '${ISOLATED_OUTDIR}/perftest-output.json'
  ]
  task_output = subprocess.check_output(
      swarming_trigger_options +
      bot_dimension_options + ['--', '--benchmarks'] +
      run_benchmark_options + output_options)
  return task_output.split('/')[-1].strip()  # return task hash


def IsTaskCompleted(task_id):
  return 'COMPLETE' in subprocess.check_output(
      [SWARMING_SCRIPT, 'query', 'tasks/get_states?task_id=%s' % task_id,
       '--swarming', SWARMING_URL])


def GetResultFromSwarming(isolate_hash, output_dir, benchmark_name, shard_id):
  """Download `perf_results.json` in the given isolate hash.

  Args:
    isolate_hash(string): the output isolate hash given by the swarming server
    output_dir(string): the dir to put the downloaded files
    benchmark_name(string): the benchmark that we ran
    shard_id(int): the shard id
  """
  # download the json that contains the description of other files
  # do not use the `--cache`, it will clear the directory
  subprocess.check_call(
      [ISOLATE_SERVER_SCRIPT, 'download',
       '--isolate-server', ISOLATE_SERVER_URL,
       '--file=%s' % isolate_hash, 'files.json', '--target=%s' % output_dir,])

  # files.json looks like:
  # {...
  # 'files': {
  #   'system_health.memory_mobile/perf_results.json': {
  #     'h': hash_num
  #     }
  #   }
  # }
  with open(os.path.join(output_dir, 'files.json')) as data:
    result_json_hash = json.load(data)['files'][
        '%s/%s' % (benchmark_name, RESULT_FILE_NAME)]['h']
    subprocess.check_call(
        [ISOLATE_SERVER_SCRIPT, 'download',
         '--isolate-server', ISOLATE_SERVER_URL,
         '--file=%s' % result_json_hash, '%d_' % shard_id + RESULT_FILE_NAME,
         '--target=%s' % output_dir,
        ])

  os.remove(os.path.join(output_dir, 'files.json'))


def CollectResults(version_task_id_table, run_label, benchmark_name):
  """Collect the result from swarming if there is task id in the table.

  This function repeatedly checks with the swarming server to see if the
  task has completed, if yes it will collect the result and update the task
  state and output isolate hash. The function terminates once all the tasks are
  completed.

  Args:
    version_task_id_table(string, list of dicts): the mapping table for the
    milestone number and the swarming jobs info. It will be like the following:
       {'version1':
         [
           {'task_hash': hash_1,
            'completed': False,
            'results_isolate': None},
           {'task_hash': hash_2,
            'completed': True,
            'results_isolate': None},
            ...
         ],
        'version2': [...]}
    In the case of running locally, all the `completed` key will be set to True.

    run_label(string): the name for the output directory, user supplies this
    when invoking the tool

    benchmark_name(string): the name of the benchmark that the user ran
  """
  while True:
    completed = True
    for version, tasks in version_task_id_table.iteritems():
      for shard_id, task in enumerate(tasks):
        if not task['completed']:
          if IsTaskCompleted(task['task_hash']):
            output = subprocess.check_output(
                [SWARMING_SCRIPT, 'query', 'task/%s/result' % task['task_hash'],
                 '--swarming', SWARMING_URL])
            output_isolate_data = json.loads(output)['outputs_ref']
            GetResultFromSwarming(
                output_isolate_data['isolated'],
                os.path.join(utils.APP_ROOT, 'results', run_label, version),
                benchmark_name,
                shard_id)
            task['results_isolate'] = output_isolate_data['isolated']
            task['completed'] = True
          else:
            completed = False
    if completed:
      break
    print 'Waiting for job to complete.'
    time.sleep(300)


def RunBenchmarkOnSwarming(apk_path):
  isolated_apk_path = IncludeAPKInIsolate(apk_path)
  GenerateIsolate(os.path.join(CHROMIUM_ROOT, 'out', 'Debug'),
                  'performance_system_chrome_test_suite')
  input_isolate_hash = UploadIsolate(os.path.join(
      CHROMIUM_ROOT, 'out', 'Debug',
      'performance_system_chrome_test_suite.isolated'))
  return TriggerSwarmingJob(input_isolate_hash, isolated_apk_path)


def RunBenchmarkLocally(apk_path, run_label):
  """Install the APK and run the benchmark on it.

  Args:
    apk_path(string): the *relative* path to the APK
    run_label(string): the name of the directory to contains all the output
    from this run
  """
  # `path_to_apk` is similar to `./out/59.0.3071.132_arm_MonochromeStable.apk`
  chrome_version = ChromeVersion(apk_path.split('/')[-1].split('_')[0])
  subprocess.check_call(['adb', 'install', '-r', '-d', apk_path])
  subprocess.check_call([os.path.join(utils.CHROMIUM_SRC, 'tools',
                                      'perf', 'run_benchmark'),
                         '--browser=android-system-chrome',
                         '--pageset-repeat=1',  # could remove this later
                         '--results-label=%s' % str(chrome_version),
                         # TODO(wangge):not sure if we should run in
                         # compatibility mode even for the later version,
                         # probably add a check in the caller to determine if
                         # we should run it in compatibility mode and add an
                         # argument `run_in_compatibility_mode` to the
                         # `RunBenchmark` function
                         '--compatibility-mode=no-field-trials',
                         '--compatibility-mode=ignore-certificate-errors',
                         '--compatibility-mode=legacy-command-line-path',
                         '--compatibility-mode=gpu-benchmarking-fallbacks',
                         '--story-filter=wikipedia',  # could remove this
                         '--output-dir=%s' % os.path.join(
                             utils.APP_ROOT, 'results', run_label,
                             str(chrome_version.milestone)),
                         'system_health.memory_mobile'])


def RunBenchmark(apk_path, run_label, use_swarming):
  """Run the benchmark.

  Args:
    apk_path(string): path to the Clank APK
    run_label(string): the user supplied label, i.e. directory name
    use_swarming(boolean): whether to run on swarming

  Returns:
    dict: containing the task meta info
  """
  task_status = {
      'task_hash': None,
      'completed': False,
      'result_isolate': None,
  }
  if use_swarming:
    task_status['task_hash'] = RunBenchmarkOnSwarming(apk_path)
  else:
    RunBenchmarkLocally(apk_path, run_label)
    task_status['completed'] = True
  return task_status
