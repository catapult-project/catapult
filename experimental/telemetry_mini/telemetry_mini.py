#!/usr/bin/env python
# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This is intended to be a very trimmed down, single-file, hackable, and easy
# to understand version of Telemetry. It's able to run a simple user story on
# Android, grab a trace, and extract memory metrics from it. May be useful to
# diagnose issues with Chrome or when trying to reproduce a regression.
#
# Known limitations: Does not use WPR, so it needs to hit the live network to
# load pages. Does not install any apks.

import argparse
import collections
import contextlib
import json
import logging
import pipes
import posixpath
import socket
import subprocess
import sys
import time
import websocket  # pylint: disable=import-error


COMMAND_LINE_FILE = '/data/local/tmp/chrome-command-line'
CHROME_PACKAGE = 'org.chromium.chrome'
MAIN_ACTIVITY = 'com.google.android.apps.chrome.Main'
STORY_URL = 'https://docs.google.com/document/d/1GvzDP-tTLmJ0myRhUAfTYWs3ZUFilUICg8psNHyccwQ/edit?usp=sharing'  # pylint: disable=line-too-long
PROFILE_DIR = '/data/data/' + CHROME_PACKAGE

BROWSER_FLAGS = [
    '--enable-heap-profiling',
    '--enable-remote-debugging',
    '--disable-fre',
    '--no-default-browser-check',
    '--no-first-run',
]

TRACE_CONFIG = {
    'excludedCategories': ['*'],
    'includedCategories': ['disabled-by-default-memory-infra'],
    'memoryDumpConfig': {'triggers': []}
}


class AdbMini(object):
  ADB_BIN = 'adb'

  @classmethod
  def RunBaseCommand(cls, *args):
    cmd = [cls.ADB_BIN]
    cmd.extend(args)
    logging.info('$ adb %s', ' '.join(pipes.quote(a) for a in args))
    return subprocess.check_output(cmd)

  @classmethod
  def GetDevices(cls):
    for line in cls.RunBaseCommand('devices').splitlines()[1:]:
      cols = line.split()
      if cols and cols[-1] == 'device':
        yield cls(cols[0])

  def __init__(self, serial):
    self._serial = serial

  def RunCommand(self, *args):
    return type(self).RunBaseCommand('-s', self._serial, *args)

  def ListPath(self, path):
    return [
        line.split(' ')[-1]
        for line in self.RunCommand('ls', path).splitlines()]

  def WriteText(self, text, path):
    self.RunCommand(
        'shell', 'echo -n %s > %s' % (pipes.quote(text), pipes.quote(path)))


def RetryOnException(exc, retries=5):
  def Decorator(f):
    def Wrapper(*args, **kwargs):
      wait = 1
      for _ in xrange(retries):
        try:
          return f(*args, **kwargs)
        except exc:
          logging.info('failed on %s, will retry ...', f.__name__)
          time.sleep(wait)
          wait *= 2
      return f(*args, **kwargs)
    return Wrapper
  return Decorator


class DevtoolsMini(object):
  def __init__(self, host, port):
    self._host = host
    self._port = port
    self._socket = None
    self._cmdid = 0

  @property
  def url(self):
    return 'ws://%s:%d/devtools/browser' % (self._host, self._port)

  def __enter__(self):
    return self.Open()

  def __exit__(self, *args, **kwargs):
    self.Close()

  @RetryOnException(socket.error)
  def Open(self):
    assert self._socket is None
    self._socket = websocket.create_connection(self.url)
    logging.info('devtools connection established')
    return self

  def Close(self):
    if self._socket is not None:
      self._socket.close()
      self._socket = None

  def RunCommand(self, method, **kwargs):
    logging.info(
        'devtools: %s(%s)', method,
        ', '.join('%s=%r' % (k, v) for k, v in sorted(kwargs.iteritems())))
    self._cmdid += 1
    self._socket.send(json.dumps(
        {'id': self._cmdid, 'method': method, 'params': kwargs}))
    resp = json.loads(self._socket.recv())
    assert resp['id'] == self._cmdid
    return resp.get('result')

  def CollectTrace(self, f):
    resp = json.loads(self._socket.recv())
    assert resp['method'] == 'Tracing.tracingComplete'
    stream_handle = resp['params']['stream']
    resp = {'eof': False}
    while not resp['eof']:
      resp = self.RunCommand('IO.read', handle=stream_handle)
      f.write(resp['data'].encode('utf-8'))
    self.RunCommand('IO.close', handle=stream_handle)


@contextlib.contextmanager
def PortForwarding(device, host_port, device_port):
  device.RunCommand('forward', '--no-rebind', host_port, device_port)
  try:
    yield
  finally:
    device.RunCommand('forward', '--remove', host_port)


@contextlib.contextmanager
def LaunchBrowser(device, startup_url):
  # Ensure it's not running before we start.
  device.RunCommand('shell', 'am', 'force-stop', CHROME_PACKAGE)
  device.RunCommand(
      'shell', 'am', 'start', '-W', '-d', startup_url,
      '-n', '/'.join([CHROME_PACKAGE, MAIN_ACTIVITY]))
  try:
    yield
  finally:
    device.RunCommand('shell', 'am', 'force-stop', CHROME_PACKAGE)


@contextlib.contextmanager
def CommandLineFlags(device, flags):
  device.WriteText(' '.join(['_'] + flags), COMMAND_LINE_FILE)
  try:
    yield
  finally:
    device.RunCommand('shell', 'rm', COMMAND_LINE_FILE)


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


def RunStory(device, run_id, args):
  tracefile = 'trace-%02d.json' % run_id

  device.RunCommand('root')
  device.RunCommand('wait-for-device')

  # Remove Chrome profile.
  remove_profile = ['shell', 'rm', '-r']
  remove_profile.extend(
      posixpath.join(PROFILE_DIR, f)
      for f in device.ListPath(PROFILE_DIR) if f not in ['.', '..', 'lib'])
  device.RunCommand(*remove_profile)

  # Flush system caches.
  device.RunCommand('shell', 'ndc', 'resolver', 'flushdefaultif')
  device.RunCommand('shell', 'sync')
  device.WriteText('3', '/proc/sys/vm/drop_caches')

  with CommandLineFlags(device, BROWSER_FLAGS):
    with LaunchBrowser(device, STORY_URL):
      with PortForwarding(
          device, 'tcp:%d' % args.port, 'localabstract:chrome_devtools_remote'):
        with DevtoolsMini(args.host, args.port) as devtools:
          devtools.RunCommand('Tracing.start', traceConfig=TRACE_CONFIG,
                              transferMode='ReturnAsStream')
          time.sleep(5)
          resp = devtools.RunCommand('Tracing.requestMemoryDump')
          assert resp['success']
          devtools.RunCommand('Tracing.end')
          with open(tracefile, 'wb') as f:
            devtools.CollectTrace(f)

  # Display metrics from any relevant process or processes.
  for p in ReadProcessMetrics(tracefile):
    if p['name'] == 'Renderer':
      print '[%d] renderer:java_heap:allocated_objects: %.2f MiB' % (
          run_id, p['java_heap'] / (1024.0 * 1024.0))


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('--adb-bin', default='adb')
  parser.add_argument('--serial')
  parser.add_argument('--pageset-repeat', type=int, default=5)
  parser.add_argument('--host', default='localhost')
  parser.add_argument('--port', type=int, default=1234)
  parser.add_argument('-v', '--verbose')
  args = parser.parse_args()

  logging.basicConfig()
  if args.verbose:
    logging.getLogger().setLevel(logging.INFO)

  AdbMini.ADB_BIN = args.adb_bin
  if args.serial is None:
    device = next(AdbMini.GetDevices())  # Use first device found.
  else:
    device = AdbMini(args.serial)

  for run_id in xrange(args.pageset_repeat):
    RunStory(device, run_id + 1, args)

if __name__ == '__main__':
  sys.exit(main())
