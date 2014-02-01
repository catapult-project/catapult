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
  def __init__(self, server_backend_class):
    assert LocalServerBackend in server_backend_class.__bases__
    server_module_name = server_backend_class.__module__
    assert server_module_name in sys.modules, \
            'The server class\' module must be findable via sys.modules'
    assert getattr(sys.modules[server_module_name],
                   server_backend_class.__name__), \
      'The server class must getattrable from its __module__ by its __name__'

    self._server_backend_class = server_backend_class
    self._subprocess = None
    self._devnull = None
    self._local_server_controller = None
    self.forwarders = None

  def Start(self, local_server_controller):
    assert self._subprocess == None
    self._local_server_controller = local_server_controller

    server_args = self.GetBackendStartupArgs()

    server_args_as_json = json.dumps(server_args)
    server_module_name = self._server_backend_class.__module__

    self._devnull = open(os.devnull, 'w')
    cmd = [sys.executable, '-m', __name__]
    cmd.extend(["run_backend"])
    cmd.extend([server_module_name, self._server_backend_class.__name__,
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
      forwarder = local_server_controller.CreateForwarder(
          named_port_pair.port)
      self.forwarders[named_port_pair.name] = forwarder

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

  @property
  def is_running(self):
    return self._subprocess != None

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
    if self._local_server_controller:
      self._local_server_controller.ServerDidClose(self)
      self._local_server_controller = None

  def GetBackendStartupArgs(self):
    """Returns whatever arguments are required to start up the backend"""
    raise NotImplementedError()


class LocalServerController():
  """Manages the list of running servers

  This class manages the running servers, but also provides an isolation layer
  to prevent LocalServer subclasses from accessing the browser backend directly.

  """
  def __init__(self, browser_backend):
    self._browser_backend = browser_backend
    self._local_servers_by_class = {}

  def StartServer(self, server):
    assert not server.is_running, 'Server already started'
    assert isinstance(server, LocalServer)
    if server.__class__ in self._local_servers_by_class:
      raise Exception(
          'Canont have two servers of the same class running at once. ' +
          'Locate the existing one and use it, or call Close() on it.')

    server.Start(self)
    self._local_servers_by_class[server.__class__] = server

  def GetRunningServer(self, server_class, default_value):
    return self._local_servers_by_class.get(server_class, default_value)

  @property
  def local_servers(self):
    return self._local_servers_by_class.values()

  def Close(self):
    while len(self._local_servers_by_class):
      server = self._local_servers_by_class.itervalues().next()
      try:
        server.Close()
      except Exception:
        import traceback
        traceback.print_exc()

  def CreateForwarder(self, port):
    return self._browser_backend.CreateForwarder(
      util.PortPair(port, self._browser_backend.GetRemotePort(port)))

  def ServerDidClose(self, server):
    del self._local_servers_by_class[server.__class__]


def _LocalServerBackendMain(args):
  assert len(args) == 4
  (cmd, server_module_name,
   server_backend_class_name, server_args_as_json) = args[:4]
  assert cmd == 'run_backend'
  server_module = __import__(server_module_name, fromlist=[True])
  server_backend_class = getattr(server_module, server_backend_class_name)
  server = server_backend_class()

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
