# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import os
import re
import socket
import subprocess
import sys

from telemetry.core import util

class NamedPortPair(object):
  def __init__(self, name, port):
    self.name = name
    self.port = port

  @staticmethod
  def FromDict(d):
    return NamedPortPair(d['name'],
                         d['port'])
  def AsDict(self):
    return {'name': self.name,
            'port': self.port}

class LocalServerBackend(object):
  def __init__(self):
    pass

  def StartAndGetNamedPortPairs(self, args):
    """Starts the actual server and obtains any sockets on which it
    should listen.

    Returns a list of NamedPortPair on which this backend is listening.
    """
    raise NotImplementedError()

  def ServeForever(self):
    raise NotImplementedError()

class LocalServer(object):
  def __init__(self, server_cls, browser_backend, server_args):
    assert LocalServerBackend in server_cls.__bases__
    server_module_name = server_cls.__module__
    assert server_module_name in sys.modules, \
            'The server class\' module must be findable via sys.modules'
    assert getattr(sys.modules[server_module_name], server_cls.__name__), \
      'The server class must getattrable from its __module__ by its __name__'
    server_args_as_json = json.dumps(server_args)

    self._subprocess = None
    self._devnull = None
    self.forwarders = None

    self._devnull = open(os.devnull, 'w')
    cmd = [sys.executable, '-m', __name__]
    cmd.extend(["run_backend"])
    cmd.extend([server_module_name, server_cls.__name__,
                server_args_as_json])

    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join(sys.path)

    cwd = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', '..'))

    self._subprocess = subprocess.Popen(
        cmd, cwd=cwd,
        env=env,
        stdout=subprocess.PIPE, stderr=sys.stderr)

    named_port_pairs = self._GetPortPairsFromBackend()

    self.forwarders = {}
    for named_port_pair in named_port_pairs:
      port = named_port_pair.port
      self.forwarders[named_port_pair.name] = browser_backend.CreateForwarder(
        util.PortPair(port, browser_backend.GetRemotePort(port)))

      def IsPortUp():
        return not socket.socket().connect_ex(('localhost', port))
      util.WaitFor(IsPortUp, 10)

  def _GetPortPairsFromBackend(self):
    named_port_pairs_json = None
    named_port_pairs_re = re.compile(
        'LocalServerBackend started: (?P<port>.+)')
    while self._subprocess.poll() == None:
      m = named_port_pairs_re.match(self._subprocess.stdout.readline())
      if m:
        named_port_pairs_json = m.group('port')
        break

    if not named_port_pairs_json:
      raise Exception('Server process died prematurely ' +
                      'without giving us port pairs.')
    return [NamedPortPair.FromDict(pair)
            for pair in json.loads(named_port_pairs_json)]

  def __enter__(self):
    return self

  def __exit__(self, *args):
    self.Close()

  def __del__(self):
    self.Close()

  def Close(self):
    if self.forwarders:
      for forwarder in self.forwarders.itervalues():
        forwarder.Close()
      self.forwarders = None
    if self._subprocess:
      # TODO(tonyg): Should this block until it goes away?
      self._subprocess.kill()
      self._subprocess = None
    if self._devnull:
      self._devnull.close()
      self._devnull = None


def _LocalServerBackendMain(args):
  assert len(args) == 4
  cmd, server_module_name, server_cls_name, server_args_as_json = args[:4]
  assert cmd == 'run_backend'
  server_module = __import__(server_module_name, fromlist=[True])
  server_cls = getattr(server_module, server_cls_name)
  server = server_cls()

  server_args = json.loads(server_args_as_json)

  named_port_pairs = server.StartAndGetNamedPortPairs(server_args)
  assert isinstance(named_port_pairs, list)
  for named_port_pair in named_port_pairs:
    assert isinstance(named_port_pair, NamedPortPair)

  # Note: This message is scraped by the parent process'
  # _GetPortPairsFromBackend(). Do **not** change it.
  print 'LocalServerBackend started: %s' % json.dumps(
    [pair.AsDict() for pair in named_port_pairs])
  sys.stdout.flush()

  return server.ServeForever()

if __name__ == '__main__':
  # This trick is needed because local_server.NamedPortPair is not the
  # same as sys.modules['__main__'].NamedPortPair. The module itself is loaded
  # twice, basically.
  from telemetry.core import local_server # pylint: disable=W0406
  sys.exit(local_server._LocalServerBackendMain( # pylint: disable=W0212
      sys.argv[1:]))
