#!/usr/bin/env python
# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This is intended to be a very trimmed down, single-file, hackable, and easy
# to understand version of Telemetry. It's able to run simple user stories on
# Android, grab traces, and extract metrics from them. May be useful to
# diagnose issues with Chrome, reproduce regressions or prototype new user
# stories.
#
# Known limitations: Does not use WPR, so it does need to hit the live network
# to load pages.

import collections
import contextlib
import functools
import httplib
import json
import logging
import os
import pipes
import posixpath
import re
import socket
import subprocess
import tempfile
import time
import websocket  # pylint: disable=import-error
from xml.etree import ElementTree as element_tree


# Parse rectangle bounds given as: '[left,top][right,bottom]'.
RE_BOUNDS = re.compile(
    r'\[(?P<left>\d+),(?P<top>\d+)\]\[(?P<right>\d+),(?P<bottom>\d+)\]')

# TODO: Maybe replace with a true on-device temp file.
UI_DUMP_TEMP = '/data/local/tmp/tm_ui_dump.xml'


def RetryOn(exc_type=(), returns_falsy=False, retries=5):
  """Decorator to retry a function in case of errors or falsy values.

  Implements exponential backoff between retries.

  Args:
    exc_type: Type of exceptions to catch and retry on. May also pass a tuple
      of exceptions to catch and retry on any of them. Defaults to catching no
      exceptions at all.
    returns_falsy: If True then the function will be retried until it stops
      returning a "falsy" value (e.g. None, False, 0, [], etc.).
    retries: Max number of retry attempts. After exhausting that number of
      attempts the function will be called with no safeguards: any exceptions
      will be raised and falsy values returned to the caller.
  """
  def Decorator(f):
    @functools.wraps(f)
    def Wrapper(*args, **kwargs):
      wait = 1
      for _ in xrange(retries):
        retry_reason = None
        try:
          value = f(*args, **kwargs)
        except exc_type as exc:
          retry_reason = 'raised %s' % type(exc).__name__
        if retry_reason is None:
          if returns_falsy and not value:
            retry_reason = 'returned %r' % value
          else:
            return value  # Success!
        logging.info('%s %s, will retry in %d second%s ...',
                     f.__name__, retry_reason, wait, '' if wait == 1 else 's')
        time.sleep(wait)
        wait *= 2
      return f(*args, **kwargs)  # Last try to run with no safeguards.
    return Wrapper
  return Decorator


class AdbCommandError(Exception):
  pass


class AdbMini(object):
  ADB_BIN = 'adb'

  @classmethod
  def RunBaseCommand(cls, *args):
    cmd = [cls.ADB_BIN]
    cmd.extend(args)
    logging.info('$ adb %s', ' '.join(pipes.quote(a) for a in args))
    return subprocess.check_output(cmd, stderr=subprocess.STDOUT)

  @classmethod
  def GetDevices(cls):
    for line in cls.RunBaseCommand('devices').splitlines()[1:]:
      cols = line.split()
      if cols and cols[-1] == 'device':
        yield cls(cols[0])

  def __init__(self, serial):
    self.serial = serial

  def RunCommand(self, *args):
    return type(self).RunBaseCommand('-s', self.serial, *args)

  def RunShellCommand(self, *args):
    return self.RunCommand('shell', *args)

  def ListPath(self, path):
    return [
        line.split(' ')[-1]
        for line in self.RunCommand('ls', path).splitlines()]

  def WriteText(self, text, path):
    self.RunShellCommand(
        'echo -n %s > %s' % (pipes.quote(text), pipes.quote(path)))

  def ListPackages(self, name_filter=None, only_enabled=False):
    """Return a list of packages available on the device."""
    args = ['pm', 'list', 'packages']
    if only_enabled:
      args.append('-e')
    if name_filter:
      args.append(name_filter)
    lines = self.RunShellCommand(*args).splitlines()
    prefix = 'package:'
    return [line[len(prefix):] for line in lines if line.startswith(prefix)]

  def ProcessStatus(self):
    """Return a defaultdict mapping of {process_name: list_of_pids}."""
    result = collections.defaultdict(list)
    # TODO: May not work on earlier Android verions without -e support.
    for line in self.RunShellCommand('ps', '-e').splitlines():
      row = line.split(None, 8)
      try:
        pid = int(row[1])
        process_name = row[-1]
      except StandardError:
        continue
      result[process_name].append(pid)
    return result

  @RetryOn(AdbCommandError)
  def GetUiDump(self):
    """Return the root XML node with screen captured from the device."""
    self.RunShellCommand('rm', '-f', UI_DUMP_TEMP)
    output = self.RunShellCommand('uiautomator', 'dump', UI_DUMP_TEMP).strip()

    if output.startswith('ERROR:'):
      # uiautomator may fail if device is not in idle state, e.g. animations
      # or video playing. Retry if that's the case.
      raise AdbCommandError(output)

    with tempfile.NamedTemporaryFile(suffix='.xml') as f:
      f.close()
      self.RunCommand('pull', UI_DUMP_TEMP, f.name)
      return element_tree.parse(f.name)

  @RetryOn(LookupError)
  def FindUiNode(self, attr_values):
    """Find a UI node on screen capture, retrying if not yet visible."""
    root = self.GetUiDump()
    for node in root.iter():
      if all(node.get(k) == v for k, v in attr_values):
        return node
    raise LookupError('Specified UI node not found')

  def TapUiNode(self, *args, **kwargs):
    node = self.FindUiNode(*args, **kwargs)
    m = RE_BOUNDS.match(node.get('bounds'))
    left, top, right, bottom = (int(v) for v in m.groups())
    x, y = (left + right) / 2, (top + bottom) / 2
    self.RunShellCommand('input', 'tap', str(x), str(y))


class DevToolsMini(object):
  def __init__(self, netloc):
    self._netloc = netloc

  def OpenWebSocket(self, path):
    if path.startswith('ws://'):
      url = path
    else:
      url = ('ws://%s/devtools/' % self._netloc) + path
    return DevToolsWebSocket(url)

  def Request(self, path=''):
    conn = httplib.HTTPConnection(self._netloc)
    try:
      url = '/json'
      if path:
        url = posixpath.join(url, path)
      conn.request('GET', url)
      response = conn.getresponse()
      payload = response.read()
      return json.loads(payload)
    finally:
      conn.close()


class DevToolsWebSocket(object):
  def __init__(self, url):
    self._url = url
    self._socket = None
    self._cmdid = 0

  def __enter__(self):
    self.Open()
    return self

  def __exit__(self, *args, **kwargs):
    self.Close()

  @RetryOn(socket.error)
  def Open(self):
    assert self._socket is None
    self._socket = websocket.create_connection(self._url)

  def Close(self):
    if self._socket is not None:
      self._socket.close()
      self._socket = None

  def Send(self, method, **kwargs):
    logging.info(
        '%s: %s(%s)', self._url, method,
        ', '.join('%s=%r' % (k, v) for k, v in sorted(kwargs.iteritems())))
    self._cmdid += 1
    self._socket.send(json.dumps(
        {'id': self._cmdid, 'method': method, 'params': kwargs}))
    resp = json.loads(self._socket.recv())
    assert resp['id'] == self._cmdid
    return resp.get('result')

  def CollectStream(self, method, f):
    resp = json.loads(self._socket.recv())
    assert resp['method'] == method
    stream_handle = resp['params']['stream']
    resp = {'eof': False}
    while not resp['eof']:
      resp = self.Send('IO.read', handle=stream_handle)
      f.write(resp['data'].encode('utf-8'))
    self.Send('IO.close', handle=stream_handle)

  @contextlib.contextmanager
  def Tracing(self, trace_config, trace_file):
    self.Send('Tracing.start', transferMode='ReturnAsStream',
              traceConfig=trace_config)
    yield self
    self.Send('Tracing.end')
    with open(trace_file, 'wb') as f:
      self.CollectStream('Tracing.tracingComplete', f)

  def RequestMemoryDump(self):
    resp = self.Send('Tracing.requestMemoryDump')
    assert resp['success']


class AndroidApp(object):
  # Override this value with path to directory where APKs to install are found.
  APKS_DIR = NotImplemented

  PACKAGE_NAME = NotImplemented
  APK_FILENAME = None

  def __init__(self, device):
    self.device = device

  def ForceStop(self):
    self.device.RunShellCommand('am', 'force-stop', self.PACKAGE_NAME)

  def Install(self):
    assert self.APK_FILENAME is not None, 'No APK to install available'
    apk_path = os.path.join(self.APKS_DIR, self.APK_FILENAME)
    logging.warning('Installing %s from %s', self.PACKAGE_NAME, apk_path)
    assert os.path.isfile(apk_path), 'File not found: %s' % apk_path
    self.device.RunCommand('install', '-r', '-d', apk_path)

  def Uninstall(self):
    logging.warning('Uninstalling %s', self.PACKAGE_NAME)
    self.device.RunCommand('uninstall', self.PACKAGE_NAME)


class ChromiumApp(AndroidApp):
  PACKAGE_NAME = 'org.chromium.chrome'
  APK_FILENAME = 'ChromePublic.apk'
  COMMAND_LINE_FILE = '/data/local/tmp/chrome-command-line'

  def RemoveProfile(self):
    # TODO: Path to profile may need to be updated on newer Android versions.
    profile_dir = posixpath.join('/data/data', self.PACKAGE_NAME)
    filenames = self.device.ListPath(profile_dir)
    args = ['rm', '-r']
    args.extend(
        posixpath.join(profile_dir, f)
        for f in filenames if f not in ['.', '..', 'lib'])
    self.device.RunShellCommand(*args)

  @contextlib.contextmanager
  def CommandLineFlags(self, flags):
    self.device.WriteText(' '.join(['_'] + flags), self.COMMAND_LINE_FILE)
    try:
      yield
    finally:
      self.device.RunShellCommand('rm', self.COMMAND_LINE_FILE)

  def GetDeviceDevToolsPort(self):
    return 'localabstract:chrome_devtools_remote'

  @contextlib.contextmanager
  def DevTools(self, host, port):
    """Setup and configure port forwarding for a DevTools instance."""
    netloc = '%s:%d' % (host, port)
    local = 'tcp:%d' % port
    remote = self.GetDeviceDevToolsPort()
    self.device.RunCommand('forward', '--no-rebind', local, remote)
    try:
      yield DevToolsMini(netloc)
    finally:
      self.device.RunCommand('forward', '--remove', local)


class ChromeApp(ChromiumApp):
  PACKAGE_NAME = 'com.google.android.apps.chrome'
  APK_FILENAME = 'Chrome.apk'


class SystemChromeApp(ChromiumApp):
  PACKAGE_NAME = 'com.android.chrome'
  APK_FILENAME = None

  def Install(self):
    # System Chrome app cannot be (un)installed, so we enable/disable instead.
    logging.warning('Enabling %s', self.PACKAGE_NAME)
    self.device.RunShellCommand('pm', 'enable', self.PACKAGE_NAME)

  def Uninstall(self):
    # System Chrome app cannot be (un)installed, so we enable/disable instead.
    logging.warning('Disabling %s', self.PACKAGE_NAME)
    self.device.RunShellCommand('pm', 'disable', self.PACKAGE_NAME)


def ReadProcessMetrics(tracefile):
  """Return a list of {"name": process_name, metric: value} dicts."""
  with open(tracefile) as f:
    trace = json.load(f)

  processes = collections.defaultdict(dict)
  for event in trace['traceEvents']:
    if event['ph'] == 'v':
      # Extract any metrics you may need from the trace.
      value = event['args']['dumps']['allocators'][
          'java_heap/allocated_objects']['attrs']['size']
      assert value['units'] == 'bytes'
      processes[event['pid']]['java_heap'] = int(value['value'], 16)
    elif event['ph'] == 'M' and event['name'] == 'process_name':
      processes[event['pid']]['name'] = event['args']['name']

  return processes.values()
