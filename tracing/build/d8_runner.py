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
import tempfile

from tvcm import parse_html_deps


_V8_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__),
    os.path.pardir, os.path.pardir, 'third_party', 'v8'))

_HTML_JS_EVAL_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), 'html2jseval.py'))

_BOOTSTRAP_JS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), 'bootstrap.js'))

_BOOTSTRAP_JS_CONTENT = None
def _GetBootStrapJsContent(search_path):
  global _BOOTSTRAP_JS_CONTENT
  if not _BOOTSTRAP_JS_CONTENT:
    with open(_BOOTSTRAP_JS_DIR, 'r') as f:
      bootstrap_js_content = f.read()
      _BOOTSTRAP_JS_CONTENT = bootstrap_js_content.replace(
          '<%html2jseval-path%>', _HTML_JS_EVAL_PATH)
  return _BOOTSTRAP_JS_CONTENT.replace('<%search-path%>',
                                       os.path.abspath(search_path))


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


def ExecuteFile(file_path, search_path=None, js_args=None):
  """ Execute javascript program in |file_path|.

  Args:
    file_path: string file_path that contains path the .js or .html file to be
      executed.
    search_path: the string absolute path of the root directory. All the imports
      in the .js or .html files must be relative to this |search_path|.
    js_args: a list of string arguments to sent to the js program.

  Returns:
    The string output from running the js program.
  """
  assert os.path.isfile(file_path)
  _, extension = os.path.splitext(file_path)
  if not extension in ('.html', '.js'):
    raise ValueError('Can only execute .js or .html file. File %s has '
                     'unsupported file type: %s' % (file_path, extension))
  if not search_path:
    search_path = os.path.dirname(file_path)

  try:
    temp_dir = tempfile.mkdtemp()
    temp_boostrap_file = os.path.join(temp_dir, '_tmp_boostrap.js')
    with open(temp_boostrap_file, 'w') as f:
      f.write(_GetBootStrapJsContent(search_path))
      if extension == '.html':
        f.write('\nloadHTML("%s");' % os.path.abspath(file_path))
      else:
        f.write('\nload("%s");' % os.path.abspath(file_path))
    return ExecuteFileWithD8(temp_boostrap_file, js_args)
  finally:
    shutil.rmtree(temp_dir)


def ExcecuteJsString(js_string, search_path, js_args=None,
                     original_file_name=None):

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
    return _ExcecuteJsFile(temp_file, search_path, js_args)
  finally:
    shutil.rmtree(temp_dir)


def ExecuteFileWithD8(js_file_path, js_args):
  """ Execute the js_files with v8 engine and return the output of the program.

  Args:
    js_file_path: the string path of the js file to be run.
    js_args: a list of arguments to passed to the |js_file_path| program.
  """
  args = [_GetD8BinaryPathForPlatform()]
  args.append(os.path.abspath(js_file_path))
  if js_args:
    args += ['--js_arguments'] + js_args
  sp = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  out, err = sp.communicate()
  if sp.returncode != 0:
    raise RuntimeError(
        "Exception raised when executing %s with args '%s':\n%s\n%s" %
        (js_file_path, js_args, out, err))
  return out


def main():
  parser = argparse.ArgumentParser(
      description='Run javascript file with v8 engine')
  parser.add_argument('file_name', help='input file', metavar='FILE',
                      type=lambda f: _IsValidJsOrHTMLFile(parser, f))
  parser.add_argument('--js_args', help='arguments for the js program',
                      nargs='+')
  parser.add_argument('--search_path', help='search path for the js program',
                      type=str)

  args = parser.parse_args()
  print ExecuteFile(args.file_name, search_path=args.search_path,
                    js_args=args.js_args)
  return 0
