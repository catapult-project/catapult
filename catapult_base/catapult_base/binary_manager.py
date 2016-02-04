# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dependency_manager  # pylint: disable=import-error


class BinaryManager(object):
  """ This class is effectively a subclass of dependency_manager, but uses a
      different number of arguments for FetchPath and LocalPath.
  """

  def __init__(self, configs):
    self._dependency_manager = dependency_manager.DependencyManager(configs)

  def FetchPath(self, binary_name, arch, platform):
    """ Return a path to the executable for <binary_name>, or None if not found.

    Will attempt to download from cloud storage if needed.
    """
    return self._dependency_manager.FetchPath(
        binary_name, '%s_%s' % (platform, arch))


  def LocalPath(self, binary_name, arch, platform):
    """ Return a local path to the given binary name, or None if not found.

    Will not download from cloud_storage.
    """
    return self._dependency_manager.LocalPath(
        binary_name, '%s_%s' % (platform, arch))
