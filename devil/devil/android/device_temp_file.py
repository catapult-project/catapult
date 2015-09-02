# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A temp file that automatically gets pushed and deleted from a device."""

# pylint: disable=W0622

import threading

from devil.android import device_errors
from devil.utils import cmd_helper

_COMMAND_TEMPLATE = (
    # Make sure that the temp dir is writable
    'test -d {dir} && '
    # If 5 random attempts fail, something is up.
    'for i in 1 2 3 4 5; do '
    'fn={dir}/{prefix}-$(date +%s)-"$RANDOM"{suffix};'
    'test -e "$fn" || break;'
    'done && '
    # Touch the file, so other temp files can't get the same name.
    'touch "$fn" && echo -n "$fn"')

class DeviceTempFile(object):
  def __init__(self, adb, suffix='', prefix='temp_file', dir='/data/local/tmp'):
    """Find an unused temporary file path in the devices external directory.

    When this object is closed, the file will be deleted on the device.

    Args:
      adb: An instance of AdbWrapper
      suffix: The suffix of the name of the temp file.
      prefix: The prefix of the name of the temp file.
      dir: The directory on the device where to place the temp file.
    """
    self._adb = adb
    command = _COMMAND_TEMPLATE.format(
        dir=cmd_helper.SingleQuote(dir),
        suffix=cmd_helper.SingleQuote(suffix),
        prefix=cmd_helper.SingleQuote(prefix))
    self.name = self._adb.Shell(command)
    self.name_quoted = cmd_helper.SingleQuote(self.name)

  def close(self):
    """Deletes the temporary file from the device."""
    # ignore exception if the file is already gone.
    def helper():
      try:
        self._adb.Shell('rm -f %s' % self.name_quoted, expect_status=None)
      except device_errors.AdbCommandFailedError:
        # file does not exist on Android version without 'rm -f' support (ICS)
        pass

    # It shouldn't matter when the temp file gets deleted, so do so
    # asynchronously.
    threading.Thread(target=helper).start()

  def __enter__(self):
    return self

  def __exit__(self, type, value, traceback):
    self.close()
