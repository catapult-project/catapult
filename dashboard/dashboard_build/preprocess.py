# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import contextlib
import logging
import os
import subprocess
import sys
import time


def _AddToPathIfNeeded(path):
  if path not in sys.path:
    sys.path.insert(0, path)


@contextlib.contextmanager
def Chdir(path):
  pwd = os.getcwd()
  try:
    yield os.chdir(path)
  finally:
    os.chdir(pwd)


def PackPinpoint(catapult_path, temp_dir, deployment_paths):
  with Chdir(catapult_path):
    _AddToPathIfNeeded(os.path.join(catapult_path, 'common', 'node_runner'))
    from node_runner import node_util
    node_path = node_util.GetNodePath()
    node_modules = node_util.GetNodeModulesPath()

    def PinpointRelativePath(*components):
      return os.path.join('dashboard', 'pinpoint', *components)

    # When packing Pinpoint, we need some extra symlinks in the temporary
    # directory, so we can find the correct elements at bundle time. This is
    # simulating the paths we would be serving as defined in the pinpoint.yaml
    # file.
    os.symlink(
        os.path.join(catapult_path, 'dashboard', 'dashboard', 'pinpoint',
                     'elements'), os.path.join(temp_dir, 'elements'))
    os.symlink(
        os.path.join(catapult_path, 'third_party', 'polymer', 'components'),
        os.path.join(temp_dir, 'components'))
    os.symlink(
        os.path.join(catapult_path, 'third_party', 'd3'),
        os.path.join(temp_dir, 'd3'))

    # We don't yet use any webpack in Pinpoint, so let's use the polymer bundler
    # for now.
    bundler_cmd = [
        node_path,
        os.path.join(node_modules, 'polymer-bundler', 'lib', 'bin',
                     'polymer-bundler.js'),
        '--inline-scripts',
        '--inline-css',
        # Exclude some paths from the bundling.
        '--exclude',
        '//fonts.googleapis.com/*',
        '--exclude',
        '//apis.google.com/*',
        # Then set up the rest of the options for the bundler.
        '--out-dir',
        os.path.join(temp_dir, 'bundled'),
        '--root',
        temp_dir,
        '--treeshake',
    ]

    # Change to the temporary directory, and run the bundler from there.
    with Chdir(temp_dir):
      bundler_cmd.extend(
          ['--in-file',
           PinpointRelativePath('index', 'index.html')])

      logging.info('Bundler Command:\n%s', ' '.join(bundler_cmd))

      proc = subprocess.Popen(
          bundler_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
      _, bundler_err = proc.communicate()
      if proc.returncode != 0:
        print('ERROR from bundler:')
        print(bundler_err)
        raise RuntimeError('Vulcanize failed with exit code', proc.returncode)

      deployment_paths.append(os.path.join(temp_dir, 'bundled'))


def PackSPA(catapult_path, temp_dir, deployment_paths):
  with Chdir(catapult_path):
    dashboard_path = os.path.join(catapult_path, 'dashboard')
    app_yaml = os.path.join(dashboard_path, 'app.yaml')
    if 'webpack/service-worker.js' not in open(app_yaml).read():
      # Only webpack if the service-worker is going to be served.
      return

    _AddToPathIfNeeded(os.path.join(catapult_path, 'common', 'node_runner'))
    from node_runner import node_util
    node_modules = node_util.GetNodeModulesPath()

    # TODO(crbug.com/918193): Remove this after migrating to lit-element.
    js_parse_filename = os.path.join(node_modules, 'hydrolysis', 'lib',
                                     'ast-utils', 'js-parse.js')
    subprocess.check_output(
        ['sed', '-i', 's/ecmaVersion: 6/ecmaVersion: 9/g', js_parse_filename])

    spa_path = os.path.join(dashboard_path, 'dashboard', 'spa')
    webpack_dir = os.path.join(temp_dir, 'webpack')
    config_filename = os.path.join(spa_path, 'webpack.config.js')
    webpack_command = os.path.join(node_modules, '.bin', 'webpack-command')

    os.environ['WEBPACK_OUTPUT_PATH'] = webpack_dir
    os.environ['WEBPACK_NODE_MODULES'] = node_modules
    os.environ['WEBPACK_THIRD_PARTY'] = os.path.join(catapult_path,
                                                     'third_party')

    proc = subprocess.Popen([webpack_command, '--config', config_filename],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    webpack_out, webpack_err = proc.communicate()
    if proc.returncode != 0:
      print('ERROR from webpack:')
      print(webpack_out)
      print(webpack_err)
      raise RuntimeError('Webpack failed with exit code', proc.returncode)

    vulcanize_cmd = [
        os.path.join(node_modules, 'vulcanize', 'bin', 'vulcanize'),
        '--strip-comments',
        '--inline-scripts',
        '--inline-css',
        '--exclude=/index.js',
    ]

    for path in sorted(deployment_paths):
      isdir = os.path.isdir(path) and not path.endswith('/')
      # Some directory names are prefixes of others. Add an explicit slash to
      # prevent confusing vulcanize.
      vulcanize_cmd.append('--redirect')
      vulcanize_cmd.append('/' + os.path.basename(path) +
                           ('/' if isdir else '') + '|' +
                           path[len(catapult_path) + 1:])

    vulcanize_cmd.append(
        os.path.join('dashboard', 'dashboard', 'spa', 'index.html'))

    proc = subprocess.Popen(
        vulcanize_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    html, vulcanize_err = proc.communicate()
    if proc.returncode != 0:
      print('ERROR from vulcanize:')
      print(vulcanize_err)
      raise RuntimeError('Vulcanize failed with exit code', proc.returncode)

    # Write the html to a temp file.
    vulcanized_index = os.path.join(temp_dir, 'index.vulcanized.html')
    open(vulcanized_index, 'w').write(html)

    minify = os.path.join(node_modules, '..', 'minify')
    subprocess.check_output([minify, vulcanized_index])

    packed_index_js_filename = os.path.join(webpack_dir, 'index.js')
    AddTimestamp(packed_index_js_filename)
    minifyjs = os.path.join(node_modules, '..', 'minifyjs')
    subprocess.check_output([minifyjs, packed_index_js_filename])
    sw_js = os.path.join(webpack_dir, 'service-worker.js')
    subprocess.check_output([minifyjs, sw_js])

    deployment_paths.append(webpack_dir)
    deployment_paths.append(vulcanized_index)


def AddTimestamp(js_name):
  # V2SPA displays its version as this timestamp in this format to make it easy
  # to check whether a change is visible.
  now = time.time()
  print('vulcanized',
        time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(now - (60 * 60 * 7))))

  js = open(js_name).read()
  with open(js_name, 'w') as fp:
    fp.write('window.VULCANIZED_TIMESTAMP=new Date(%d);\n' % (now * 1000))
    fp.write(js)
