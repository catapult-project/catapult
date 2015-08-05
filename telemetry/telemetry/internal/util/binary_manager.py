# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from catapult_base import support_binaries


def FetchPath(binary_name, platform, arch):
  """ Return a path to the appropriate executable for <binary_name>, downloading
      from cloud storage if needed, or None if it cannot be found.
  """
  return support_binaries.FindPath(binary_name, platform, arch)

def LocalPath(binary_name, platform, arch):
  """ Return a local path to the given binary name, or None if an executable
      cannot be found. Will not download the executable.
      """
  del platform, arch
  return support_binaries.FindLocallyBuiltPath(binary_name)
