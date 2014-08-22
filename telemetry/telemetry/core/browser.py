# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from telemetry import decorators
from telemetry.core import browser_credentials
from telemetry.core import exceptions
from telemetry.core import extension_dict
from telemetry.core import local_server
from telemetry.core import memory_cache_http_server
from telemetry.core import tab_list
from telemetry.core import wpr_modes
from telemetry.core import wpr_server
from telemetry.core.backends import browser_backend
from telemetry.core.platform.profiler import profiler_finder


class Browser(object):
  """A running browser instance that can be controlled in a limited way.

  To create a browser instance, use browser_finder.FindBrowser.

  Be sure to clean up after yourself by calling Close() when you are done with
  the browser. Or better yet:
    browser_to_create = FindBrowser(options)
    with browser_to_create.Create() as browser:
      ... do all your operations on browser here
  """
  def __init__(self, backend, platform_backend):
    assert platform_backend.platform != None

    self._browser_backend = backend
    self._platform_backend = platform_backend
    self._wpr_server = None
    self._active_profilers = []
    self._profilers_states = {}
    self._local_server_controller = local_server.LocalServerController(backend)
    self._tabs = tab_list.TabList(backend.tab_list_backend)
    self.credentials = browser_credentials.BrowserCredentials()

    self._platform_backend.DidCreateBrowser(self, self._browser_backend)

  def __enter__(self):
    self.Start()
    return self

  def __exit__(self, *args):
    self.Close()

  @property
  def platform(self):
    return self._platform_backend.platform

  @property
  def browser_type(self):
    return self._browser_backend.browser_type

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

  def is_profiler_active(self, profiler_name):
    return profiler_name in [profiler.name() for
                             profiler in self._active_profilers]

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

    # We want a single time value, not the sum for all processes.
    cpu_timestamp = self._platform_backend.GetCpuTimestamp()
    for process_type in result:
      # Skip any process_types that are empty
      if not len(result[process_type]):
        continue
      result[process_type].update(cpu_timestamp)
    return result

  @property
  def io_stats(self):
    """Returns a dict of IO statistics for the browser:
    { 'Browser': {
        'ReadOperationCount': W,
        'WriteOperationCount': X,
        'ReadTransferCount': Y,
        'WriteTransferCount': Z
      },
      'Gpu': {
        'ReadOperationCount': W,
        'WriteOperationCount': X,
        'ReadTransferCount': Y,
        'WriteTransferCount': Z
      },
      'Renderer': {
        'ReadOperationCount': W,
        'WriteOperationCount': X,
        'ReadTransferCount': Y,
        'WriteTransferCount': Z
      }
    }
    """
    result = self._GetStatsCommon(self._platform_backend.GetIOStats)
    del result['ProcessCount']
    return result

  def StartProfiling(self, profiler_name, base_output_file):
    """Starts profiling using |profiler_name|. Results are saved to
    |base_output_file|.<process_name>."""
    assert not self._active_profilers, 'Already profiling. Must stop first.'

    profiler_class = profiler_finder.FindProfiler(profiler_name)

    if not profiler_class.is_supported(self._browser_backend.browser_type):
      raise Exception('The %s profiler is not '
                      'supported on this platform.' % profiler_name)

    if not profiler_class in self._profilers_states:
      self._profilers_states[profiler_class] = {}

    self._active_profilers.append(
        profiler_class(self._browser_backend, self._platform_backend,
            base_output_file, self._profilers_states[profiler_class]))

  def StopProfiling(self):
    """Stops all active profilers and saves their results.

    Returns:
      A list of filenames produced by the profiler.
    """
    output_files = []
    for profiler in self._active_profilers:
      output_files.extend(profiler.CollectProfile())
    self._active_profilers = []
    return output_files

  def Start(self):
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

  def Close(self):
    """Closes this browser."""
    for profiler_class in self._profilers_states:
      profiler_class.WillCloseBrowser(self._browser_backend,
                                      self._platform_backend)

    if self._browser_backend.IsBrowserRunning():
      self._platform_backend.WillCloseBrowser(self, self._browser_backend)

    if self._wpr_server:
      self._wpr_server.Close()
      self._wpr_server = None

    self._local_server_controller.Close()
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

  def SetReplayArchivePath(self, archive_path, append_to_existing_wpr=False,
                           make_javascript_deterministic=True):
    if self._wpr_server:
      self._wpr_server.Close()
      self._wpr_server = None

    if not archive_path:
      return None

    if self._browser_backend.wpr_mode == wpr_modes.WPR_OFF:
      return

    use_record_mode = self._browser_backend.wpr_mode == wpr_modes.WPR_RECORD
    if not use_record_mode:
      assert os.path.isfile(archive_path)

    self._wpr_server = wpr_server.ReplayServer(
        self._browser_backend,
        archive_path,
        use_record_mode,
        append_to_existing_wpr,
        make_javascript_deterministic)

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
