# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import httplib
import os
import json
import re
import socket
import subprocess
import sys
import urlparse
import time

from tvcm import dev_server

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

class TemporaryDevServer(object):
  def __init__(self):
    self._port = None
    self._server = None

    cmd = [sys.executable, '-m', __name__]
    env = os.environ.copy()
    env['PYTHONPATH'] = os.path.abspath(
      os.path.join(os.path.dirname(__file__), '..'))

    self._server = subprocess.Popen(cmd, cwd=os.getcwd(),
                                    env=env, stdout=subprocess.PIPE, stderr=sys.stderr)

    port_re = re.compile(
        'TemporaryDevServer started on port (?P<port>\d+)')
    while self._server.poll() == None:
      line = self._server.stdout.readline()
      m = port_re.match(line)
      if m:
        self._port = int(m.group('port'))
        break
    if not self._port:
      raise Exception('Couldn\'t start')

    def IsServerUp():
      return not socket.socket().connect_ex(('localhost', self._port))
    WaitFor(IsServerUp, 10)

  @property
  def port(self):
    return self._port

  def __del__(self):
    self.Close()

  def Close(self):
    if self._server:
      # TODO(tonyg): Should this block until it goes away?
      if self._server.poll() == None:
        self._server.kill()
      self._server = None

  @property
  def url(self):
    return 'http://localhost:%i/' % self._port

  def Get(self, path, expected_response_code=200):
    conn = httplib.HTTPConnection('localhost', self.port, True)
    conn.connect()
    conn.request('GET', path)
    resp = conn.getresponse()
    resp_str = resp.read(resp.getheader('Content-Length'))
    if resp.status != expected_response_code:
      try:
        resp_data = json.loads(resp_str)
      except ValueError:
        resp_data = {}
      if 'details' in resp_data:
        sys.stderr.write(resp_data['details'])
        sys.stderr.write('\n')
        raise Exception('Expected status %i, got %i', expected_response_code, resp.status)
      else:
        raise Exception('Expected status %i, got %i: %s', expected_response_code, resp.status, resp_str)
    return resp_str

  def CallOnServer(self, method_name, *args):
    arg_string = ','.join([repr(arg) for arg in args])
    data = 'self.%s(%s)' % (method_name, arg_string)

    conn = httplib.HTTPConnection('localhost', self.port, True)
    conn.connect()
    conn.request('POST', '/test/customize', data)
    resp = conn.getresponse()
    resp_str = resp.read(resp.getheader('Content-Length'))
    if resp.status != 200:
      resp_data = json.loads(resp_str)
      sys.stderr.write(resp_data['details'])
      sys.stderr.write('\n')
      assert False
    return resp_str


def _do_POST_customize(request):
  if 'Content-Length' in request.headers:
    cl = int(request.headers['Content-Length'])
    text = request.rfile.read(cl).encode('utf8')

    eval(text, {}, {'self': request.server})
    data = 'ok'
    request.send_response(200)
    request.send_header('Content-Type', 'text/plain')
    request.send_header('Content-Length', len(data))
    request.end_headers()
    request.wfile.write(data)

def SubprocessMain(args):
  port=GetUnreservedAvailableLocalPort()
  server = dev_server.DevServer(port=port, quiet=True)

  server.AddPathHandler('/test/customize', _do_POST_customize,
                        supports_get=False,
                        supports_post=True)
  sys.stdout.write('TemporaryDevServer started on port %i\n' % port)
  sys.stdout.flush() # This is key! It kicks the port detector above.
  server.serve_forever()

if __name__ == '__main__':
  sys.exit(SubprocessMain(sys.argv[1:]))
