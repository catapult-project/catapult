#!/usr/bin/env python
# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import os
import subprocess
import StringIO
import sys
import platform


_V8_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__),
    os.path.pardir, os.path.pardir, 'third_party', 'v8'))


def _IsValidJsFile(parser, js_file_arg):
  if not os.path.exists(js_file_arg):
    parser.error('The file %s does not exist' % js_file_arg)
  _, extension = os.path.splitext(js_file_arg)
  if extension != '.js':
    parser.error('Input must be a javascript file')
  return js_file_arg


def _GetD8BinaryPathForPlatform():
  if platform.system() == 'Linux' and platform.machine() == 'x86_64':
    return os.path.join(_V8_DIR, 'linux', 'x86_64', 'd8')
  elif platform.system() == 'Darwin' and platform.machine() == 'x86_64':
    return os.path.join(_V8_DIR, 'mac', 'x86_64', 'd8')
  else:
    raise NotImplementedError(
        'd8 binary for this platform and architecture is not yet supported')


def ExcecuteJsFile(js_file_name, js_args):
  """ Execute the js_file with v8 engine and return the output of the program.

  Args:
    js_file_name: the string name of the js file to be run.
    js_args: a list of arguments to passed to the |js_file_name| program.
  """
  args = [_GetD8BinaryPathForPlatform()]
  args.append(js_file_name)
  if js_args:
    args += ['--js_arguments'] + js_args
  sp = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  out, err = sp.communicate()
  if sp.returncode != 0:
    raise RuntimeError(
        "Exception raised when executing %s with args '%s':\n%s\n%s" %
        (js_file_name, js_args, out, err))
  return out


def main():
  parser = argparse.ArgumentParser(
      description='Run javascript file with v8 engine')
  parser.add_argument('js_file_name', help='input js file', metavar='JS_FILE',
                      type=lambda f: _IsValidJsFile(parser, f))
  parser.add_argument('--js_args', help='arguments for the js program',
                      nargs='+')
  args = parser.parse_args()

  print ExcecuteJsFile(args.js_file_name, args.js_args)
  return 0
