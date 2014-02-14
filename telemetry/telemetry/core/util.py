# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import inspect
import logging
import os
import socket
import sys
import time


class TimeoutException(Exception):
  pass


def GetBaseDir():
  main_module = sys.modules['__main__']
  if hasattr(main_module, '__file__'):
    return os.path.dirname(os.path.realpath(main_module.__file__))
  else:
    return os.getcwd()


def GetTelemetryDir():
  return os.path.normpath(os.path.join(
      os.path.realpath(__file__), os.pardir, os.pardir, os.pardir))


def GetUnittestDataDir():
  return os.path.join(GetTelemetryDir(), 'unittest_data')


def GetChromiumSrcDir():
  return os.path.normpath(os.path.join(GetTelemetryDir(), os.pardir, os.pardir))


def AddDirToPythonPath(*path_parts):
  path = os.path.abspath(os.path.join(*path_parts))
  if os.path.isdir(path) and path not in sys.path:
    sys.path.append(path)


def WaitFor(condition, timeout):
  """Waits for up to |timeout| secs for the function |condition| to return True.

  Polling frequency is (elapsed_time / 10), with a min of .1s and max of 5s.

  Returns:
    Result of |condition| function (if present).
  """
  min_poll_interval =   0.1
  max_poll_interval =   5
  output_interval   = 300

  def GetConditionString():
    if condition.__name__ == '<lambda>':
      try:
        return inspect.getsource(condition).strip()
      except IOError:
        pass
    return condition.__name__

  start_time = time.time()
  last_output_time = start_time
  while True:
    res = condition()
    if res:
      return res
    now = time.time()
    elapsed_time = now - start_time
    last_output_elapsed_time = now - last_output_time
    if elapsed_time > timeout:
      raise TimeoutException('Timed out while waiting %ds for %s.' %
                             (timeout, GetConditionString()))
    if last_output_elapsed_time > output_interval:
      logging.info('Continuing to wait %ds for %s. Elapsed: %ds.',
                   timeout, GetConditionString(), elapsed_time)
      last_output_time = time.time()
    poll_interval = min(max(elapsed_time / 10., min_poll_interval),
                        max_poll_interval)
    time.sleep(poll_interval)


def FindElementAndPerformAction(tab, text, callback_code):
  """JavaScript snippet for finding an element with a given text on a page."""
  code = """
      (function() {
        var callback_function = """ + callback_code + """;
        function _findElement(element, text) {
          if (element.innerHTML == text) {
            callback_function
            return element;
          }
          for (var i in element.childNodes) {
            var found = _findElement(element.childNodes[i], text);
            if (found)
              return found;
          }
          return null;
        }
        var _element = _findElement(document, \"""" + text + """\");
        return callback_function(_element);
      })();"""
  return tab.EvaluateJavaScript(code)


def GetUnreservedAvailableLocalPort():
  """Returns an available port on the system.

  WARNING: This method does not reserve the port it returns, so it may be used
  by something else before you get to use it. This can lead to flake.
  """
  tmp = socket.socket()
  tmp.bind(('', 0))
  port = tmp.getsockname()[1]
  tmp.close()

  return port


def CloseConnections(tab):
  """Closes all TCP sockets held open by the browser."""
  try:
    tab.ExecuteJavaScript("""window.chrome && chrome.benchmarking &&
                             chrome.benchmarking.closeConnections()""")
  except Exception:
    pass


def GetBuildDirectories():
  """Yields all combination of Chromium build output directories."""
  build_dirs = ['build',
                os.path.basename(os.environ.get('CHROMIUM_OUT_DIR', 'out')),
                'xcodebuild']

  build_types = ['Debug', 'Debug_x64', 'Release', 'Release_x64']

  for build_dir in build_dirs:
    for build_type in build_types:
      yield build_dir, build_type

def FindSupportBinary(binary_name, executable=True):
  """Returns the path to the given binary name."""
  # TODO(tonyg/dtu): This should support finding binaries in cloud storage.
  command = None
  command_mtime = 0
  required_mode = os.R_OK
  if executable:
    required_mode = os.X_OK

  chrome_root = GetChromiumSrcDir()
  for build_dir, build_type in GetBuildDirectories():
    candidate = os.path.join(chrome_root, build_dir, build_type, binary_name)
    if os.path.isfile(candidate) and os.access(candidate, required_mode):
      candidate_mtime = os.stat(candidate).st_mtime
      if candidate_mtime > command_mtime:
        command = candidate
        command_mtime = candidate_mtime

  return command
