# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from telemetry.core import app
from telemetry.core.backends import browser_backend
from telemetry.core import browser_credentials
from telemetry.core import exceptions
from telemetry.core import extension_dict
from telemetry.core import local_server
from telemetry.core import memory_cache_http_server
from telemetry.core.platform import profiling_controller
from telemetry.core import tab_list
from telemetry import decorators


class Browser(app.App):
  """A running browser instance that can be controlled in a limited way.

  To create a browser instance, use browser_finder.FindBrowser.

  Be sure to clean up after yourself by calling Close() when you are done with
  the browser. Or better yet:
    browser_to_create = FindBrowser(options)
    with browser_to_create.Create(options) as browser:
      ... do all your operations on browser here
  """
  def __init__(self, backend, platform_backend, credentials_path):
    super(Browser, self).__init__(app_backend=backend,
                                  platform_backend=platform_backend)
    self._browser_backend = backend
    self._platform_backend = platform_backend
    self._local_server_controller = local_server.LocalServerController(
        platform_backend)
    self._tabs = tab_list.TabList(backend.tab_list_backend)
    self.credentials = browser_credentials.BrowserCredentials()
    self.credentials.credentials_path = credentials_path
    self._platform_backend.DidCreateBrowser(self, self._browser_backend)

    browser_options = self._browser_backend.browser_options
    self.platform.FlushDnsCache()
    if browser_options.clear_sytem_cache_for_browser_and_profile_on_start:
      if self.platform.CanFlushIndividualFilesFromSystemCache():
        self.platform.FlushSystemCacheForDirectory(
            self._browser_backend.profile_directory)
        self.platform.FlushSystemCacheForDirectory(
            self._browser_backend.browser_directory)
      else:
        self.platform.FlushEntireSystemCache()

    self._browser_backend.SetBrowser(self)
    self._browser_backend.Start()
    self._platform_backend.DidStartBrowser(self, self._browser_backend)
    self._profiling_controller = profiling_controller.ProfilingController(
        self._browser_backend.profiling_controller_backend)

  @property
  def profiling_controller(self):
    return self._profiling_controller

  @property
  def browser_type(self):
    return self.app_type

  @property
  def supports_extensions(self):
    return self._browser_backend.supports_extensions

  @property
  def supports_tab_control(self):
    return self._browser_backend.supports_tab_control

  @property
  def synthetic_gesture_source_type(self):
    return self._browser_backend.browser_options.synthetic_gesture_source_type

  @property
  def tabs(self):
    return self._tabs

  @property
  def foreground_tab(self):
    for i in xrange(len(self._tabs)):
      # The foreground tab is the first (only) one that isn't hidden.
      # This only works through luck on Android, due to crbug.com/322544
      # which means that tabs that have never been in the foreground return
      # document.hidden as false; however in current code the Android foreground
      # tab is always tab 0, which will be the first one that isn't hidden
      if self._tabs[i].EvaluateJavaScript('!document.hidden'):
        return self._tabs[i]
    raise Exception("No foreground tab found")

  @property
  @decorators.Cache
  def extensions(self):
    if not self.supports_extensions:
      raise browser_backend.ExtensionsNotSupportedException(
          'Extensions not supported')
    return extension_dict.ExtensionDict(self._browser_backend.extension_backend)

  def _GetStatsCommon(self, pid_stats_function):
    browser_pid = self._browser_backend.pid
    result = {
        'Browser': dict(pid_stats_function(browser_pid), **{'ProcessCount': 1}),
        'Renderer': {'ProcessCount': 0},
        'Gpu': {'ProcessCount': 0},
        'Other': {'ProcessCount': 0}
    }
    process_count = 1
    for child_pid in self._platform_backend.GetChildPids(browser_pid):
      try:
        child_cmd_line = self._platform_backend.GetCommandLine(child_pid)
        child_stats = pid_stats_function(child_pid)
      except exceptions.ProcessGoneException:
        # It is perfectly fine for a process to have gone away between calling
        # GetChildPids() and then further examining it.
        continue
      child_process_name = self._browser_backend.GetProcessName(child_cmd_line)
      process_name_type_key_map = {'gpu-process': 'Gpu', 'renderer': 'Renderer'}
      if child_process_name in process_name_type_key_map:
        child_process_type_key = process_name_type_key_map[child_process_name]
      else:
        # TODO: identify other process types (zygote, plugin, etc), instead of
        # lumping them in a single category.
        child_process_type_key = 'Other'
      result[child_process_type_key]['ProcessCount'] += 1
      for k, v in child_stats.iteritems():
        if k in result[child_process_type_key]:
          result[child_process_type_key][k] += v
        else:
          result[child_process_type_key][k] = v
      process_count += 1
    for v in result.itervalues():
      if v['ProcessCount'] > 1:
        for k in v.keys():
          if k.endswith('Peak'):
            del v[k]
      del v['ProcessCount']
    result['ProcessCount'] = process_count
    return result

  @property
  def memory_stats(self):
    """Returns a dict of memory statistics for the browser:
    { 'Browser': {
        'VM': R,
        'VMPeak': S,
        'WorkingSetSize': T,
        'WorkingSetSizePeak': U,
        'ProportionalSetSize': V,
        'PrivateDirty': W
      },
      'Gpu': {
        'VM': R,
        'VMPeak': S,
        'WorkingSetSize': T,
        'WorkingSetSizePeak': U,
        'ProportionalSetSize': V,
        'PrivateDirty': W
      },
      'Renderer': {
        'VM': R,
        'VMPeak': S,
        'WorkingSetSize': T,
        'WorkingSetSizePeak': U,
        'ProportionalSetSize': V,
        'PrivateDirty': W
      },
      'SystemCommitCharge': X,
      'SystemTotalPhysicalMemory': Y,
      'ProcessCount': Z,
    }
    Any of the above keys may be missing on a per-platform basis.
    """
    self._platform_backend.PurgeUnpinnedMemory()
    result = self._GetStatsCommon(self._platform_backend.GetMemoryStats)
    commit_charge = self._platform_backend.GetSystemCommitCharge()
    if commit_charge:
      result['SystemCommitCharge'] = commit_charge
    total = self._platform_backend.GetSystemTotalPhysicalMemory()
    if total:
      result['SystemTotalPhysicalMemory'] = total
    return result

  @property
  def cpu_stats(self):
    """Returns a dict of cpu statistics for the system.
    { 'Browser': {
        'CpuProcessTime': S,
        'TotalTime': T
      },
      'Gpu': {
        'CpuProcessTime': S,
        'TotalTime': T
      },
      'Renderer': {
        'CpuProcessTime': S,
        'TotalTime': T
      }
    }
    Any of the above keys may be missing on a per-platform basis.
    """
    result = self._GetStatsCommon(self._platform_backend.GetCpuStats)
    del result['ProcessCount']

    # FIXME: Renderer process CPU times are impossible to compare correctly.
    # http://crbug.com/419786#c11
    if 'Renderer' in result:
      del result['Renderer']

    # We want a single time value, not the sum for all processes.
    cpu_timestamp = self._platform_backend.GetCpuTimestamp()
    for process_type in result:
      # Skip any process_types that are empty
      if not len(result[process_type]):
        continue
      result[process_type].update(cpu_timestamp)
    return result

  def Close(self):
    """Closes this browser."""
    if self._browser_backend.IsBrowserRunning():
      self._platform_backend.WillCloseBrowser(self, self._browser_backend)

    self._local_server_controller.Close()
    self._browser_backend.profiling_controller_backend.WillCloseBrowser()
    self._browser_backend.Close()
    self.credentials = None

  @property
  def http_server(self):
    return self._local_server_controller.GetRunningServer(
        memory_cache_http_server.MemoryCacheHTTPServer, None)

  def SetHTTPServerDirectories(self, paths):
    """Returns True if the HTTP server was started, False otherwise."""
    if isinstance(paths, basestring):
      paths = set([paths])
    paths = set(os.path.realpath(p) for p in paths)

    # If any path is in a subdirectory of another, remove the subdirectory.
    duplicates = set()
    for parent_path in paths:
      for sub_path in paths:
        if parent_path == sub_path:
          continue
        if os.path.commonprefix((parent_path, sub_path)) == parent_path:
          duplicates.add(sub_path)
    paths -= duplicates

    if self.http_server:
      if paths and self.http_server.paths == paths:
        return False

      self.http_server.Close()

    if not paths:
      return False

    server = memory_cache_http_server.MemoryCacheHTTPServer(paths)
    self.StartLocalServer(server)
    return True

  def StartLocalServer(self, server):
    """Starts a LocalServer and associates it with this browser.

    It will be closed when the browser closes.
    """
    self._local_server_controller.StartServer(server)

  @property
  def local_servers(self):
    """Returns the currently running local servers."""
    return self._local_server_controller.local_servers

  def GetStandardOutput(self):
    return self._browser_backend.GetStandardOutput()

  def GetStackTrace(self):
    return self._browser_backend.GetStackTrace()

  @property
  def supports_system_info(self):
    return self._browser_backend.supports_system_info

  def GetSystemInfo(self):
    """Returns low-level information about the system, if available.

       See the documentation of the SystemInfo class for more details."""
    return self._browser_backend.GetSystemInfo()
