#!/usr/bin/env python
# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import os
import platform
import shutil
import subprocess
import StringIO
import sys
import json
import tempfile

from tvcm import parse_html_deps


_V8_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__),
    os.path.pardir, os.path.pardir, 'tracing', 'third_party', 'v8'))

_HTML_JS_EVAL_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), 'html2jseval.py'))

_BOOTSTRAP_JS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), 'd8_bootstrap.js'))

_PATH_UTILS_JS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), 'path_utils.js'))

_BOOTSTRAP_JS_CONTENT = None
def _ValidateSourcePaths(source_paths):
  if source_paths is None:
    return
  for x in source_paths:
    assert os.path.exists(x)
    assert os.path.isdir(x)
    assert os.path.isabs(x)

def _GetBootStrapJsContent(source_paths):
  global _BOOTSTRAP_JS_CONTENT
  if not _BOOTSTRAP_JS_CONTENT:
    with open(_BOOTSTRAP_JS_DIR, 'r') as f:
      bootstrap_js_content = f.read()
      _BOOTSTRAP_JS_CONTENT = bootstrap_js_content.replace(
          '<%html2jseval-path%>', _HTML_JS_EVAL_PATH)


  bsc = _BOOTSTRAP_JS_CONTENT

  source_path_string = json.dumps(source_paths)
  bsc = bsc.replace('<%source_paths%>', source_path_string)
  bsc = bsc.replace('<%current_working_directory%>', os.getcwd())
  bsc = bsc.replace('<%path_utils_js_path%>', _PATH_UTILS_JS_DIR)
  return bsc


def _IsValidJsOrHTMLFile(parser, js_file_arg):
  if not os.path.exists(js_file_arg):
    parser.error('The file %s does not exist' % js_file_arg)
  _, extension = os.path.splitext(js_file_arg)
  if extension not in ('.js', '.html'):
    parser.error('Input must be a JavaScript or HTML file')
  return js_file_arg


def _GetD8BinaryPathForPlatform():
  if platform.system() == 'Linux' and platform.machine() == 'x86_64':
    return os.path.join(_V8_DIR, 'linux', 'x86_64', 'd8')
  elif platform.system() == 'Darwin' and platform.machine() == 'x86_64':
    return os.path.join(_V8_DIR, 'mac', 'x86_64', 'd8')
  else:
    raise NotImplementedError(
        'd8 binary for this platform and architecture is not yet supported')

class RunResult(object):
  def __init__(self, returncode, stdout):
    self.returncode = returncode
    self.stdout = stdout

def ExecuteFile(file_path, source_paths=None, js_args=None):
  """ Execute javascript program in |file_path|.

  Args:
    file_path: string file_path that contains path the .js or .html file to be
      executed.
    source_paths: the list of absolute paths containing code. All the imports
    js_args: a list of string arguments to sent to the js program.

  Returns:
     The string output from running the js program.
  """
  res = RunFile(file_path, source_paths, js_args)
  return res.stdout

def RunFile(file_path, source_paths=None, js_args=None):
  """ Runs javascript program in |file_path|.

  Args are same as ExecuteFile.

  Returns:
     A RunResult containing the program's output.
  """
  assert os.path.isfile(file_path)
  _ValidateSourcePaths(source_paths)

  _, extension = os.path.splitext(file_path)
  if not extension in ('.html', '.js'):
    raise ValueError('Can only execute .js or .html file. File %s has '
                     'unsupported file type: %s' % (file_path, extension))
  if source_paths is None:
    source_paths = [os.path.dirname(file_path)]

  abs_file_path = os.path.abspath(file_path)

  try:
    temp_dir = tempfile.mkdtemp()
    temp_boostrap_file = os.path.join(temp_dir, '_tmp_boostrap.js')
    with open(temp_boostrap_file, 'w') as f:
      f.write(_GetBootStrapJsContent(source_paths))
      if extension == '.html':
        f.write('\nloadHTMLFile("%s");' % abs_file_path)
      else:
        f.write('\nloadFile("%s");' % abs_file_path)
    return _RunFileWithD8(temp_boostrap_file, js_args)
  finally:
    shutil.rmtree(temp_dir)


def ExcecuteJsString(js_string, source_paths=None, js_args=None,
                     original_file_name=None):
  res = RunJsString(js_string, source_paths, js_args, original_file_name)
  return res.stdout

def RunJsString(js_string, source_paths=None, js_args=None,
                     original_file_name=None):
  _ValidateSourcePaths(source_paths)

  try:
    temp_dir = tempfile.mkdtemp()
    if original_file_name:
      name = os.path.basename(original_file_name)
      name, _ = os.path.splitext(name)
      temp_file = os.path.join(temp_dir, '%s.js' % name)
    else:
      temp_file = os.path.join(temp_dir, 'temp_program.js')
    with open(temp_file, 'w') as f:
      f.write(js_string)
    return RunFile(temp_file, source_paths, js_args)
  finally:
    shutil.rmtree(temp_dir)


def _RunFileWithD8(js_file_path, js_args):
  """ Execute the js_files with v8 engine and return the output of the program.

  Args:
    js_file_path: the string path of the js file to be run.
    js_args: a list of arguments to passed to the |js_file_path| program.
  """
  args = [_GetD8BinaryPathForPlatform()]
  args.append(os.path.abspath(js_file_path))
  full_js_args = [args[0]]
  if js_args:
    full_js_args += js_args

  args += ['--js_arguments'] + full_js_args
  sp = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
  out, err = sp.communicate()
  assert err is None

  # d8 uses returncode 1 to indicate an uncaught exception, but
  # _RunFileWithD8 needs to distingiush between that and quit(1).
  #
  # To fix this, d8_bootstrap.js monkeypatches D8's quit function to
  # adds 1 to an intentioned nonzero quit. So, now, we have to undo this
  # logic here in order to raise/return the right thing.
  returncode = sp.returncode
  if returncode == 0:
    return RunResult(0, out)
  elif returncode == 1:
    raise RuntimeError(
        "Exception raised when executing %s:\n%s" %
        (js_file_path, out))
  else:
    return RunResult(returncode - 1, out)


def main():
  parser = argparse.ArgumentParser(
      description='Run javascript file with v8 engine')
  parser.add_argument('file_name', help='input file', metavar='FILE',
                      type=lambda f: _IsValidJsOrHTMLFile(parser, f))
  parser.add_argument('--js_args', help='arguments for the js program',
                      nargs='+')
  parser.add_argument('--source_paths', help='search path for the js program',
                      nargs='+', type=str)

  args = parser.parse_args()

  args.source_paths = [os.path.abspath(x) for x in args.source_paths]
  res = RunFile(args.file_name, source_paths=args.source_paths,
                js_args=args.js_args)
  print res.stdout
  return res.returncode
