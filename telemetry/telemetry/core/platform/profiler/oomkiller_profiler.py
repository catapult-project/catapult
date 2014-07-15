# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from telemetry.core import util
from telemetry.core.backends.chrome import android_browser_finder
from telemetry.core.platform import profiler
from telemetry.util import support_binaries

util.AddDirToPythonPath(util.GetChromiumSrcDir(), 'build', 'android')
from pylib.device import intent  # pylint: disable=F0401

class UnableToFindApplicationException(Exception):
  """Exception when unable to find a launched application"""

  def __init__(self, application):
    super(UnableToFindApplicationException, self).__init__()
    self.application = application

  def __str__(self):
    return repr(self.application)


class OOMKillerProfiler(profiler.Profiler):
  """Android-specific, Launch the music application and check it is still alive
  at the end of the run."""

  def __init__(self, browser_backend, platform_backend, output_path, state):
    super(OOMKillerProfiler, self).__init__(
        browser_backend, platform_backend, output_path, state)
    if not 'mem_consumer_launched' in state:
      state['mem_consumer_launched'] = True
      mem_consumer_path = support_binaries.FindPath(
          os.path.join('apks', 'MemConsumer.apk'), 'android')
      assert mem_consumer_path, ('Could not find memconsumer app. Please build '
                                 'memconsumer target.')
      self._browser_backend.adb.Install(mem_consumer_path)
      self._browser_backend.adb.device().GoHome()
      self._platform_backend.LaunchApplication(
          'org.chromium.memconsumer/.MemConsumer',
          '--ei memory 20')
      # Bring the browser to the foreground after launching the mem consumer
      self._browser_backend.adb.device().StartActivity(
          intent.Intent(package=browser_backend.package,
                        activity=browser_backend.activity),
          blocking=True)

  @classmethod
  def name(cls):
    return 'oomkiller'

  @classmethod
  def is_supported(cls, browser_type):
    if browser_type == 'any':
      return android_browser_finder.CanFindAvailableBrowsers()
    return browser_type.startswith('android')

  @classmethod
  def WillCloseBrowser(cls, browser_backend, platform_backend):
    browser_backend.adb.device().ForceStop('org.chromium.memconsumer')

  def CollectProfile(self):
    missing_applications = self._MissingApplications()
    if not len(missing_applications):
      return []
    raise UnableToFindApplicationException(', '.join(missing_applications))

  def _MissingApplications(self):
    # TODO(qsr): Add com.android.launcher to the list, when the reason why the
    # launcher is often killed is understood.
    must_have_apps = [
        'org.chromium.memconsumer',
    ]
    return [app for app in must_have_apps if
            not self._platform_backend.IsApplicationRunning(app)]
