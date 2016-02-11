# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

import dependency_manager


class BinaryManager(object):
  """ This class is effectively a subclass of dependency_manager, but uses a
      different number of arguments for FetchPath and LocalPath.
  """

  def __init__(self, configs):
    self._dependency_manager = dependency_manager.DependencyManager(configs)

  def FetchPath(self, binary_name, arch, os_name, os_version=None):
    """ Return a path to the executable for <binary_name>, or None if not found.

    Will attempt to download from cloud storage if needed.
    """
    platform = '%s_%s' % (os_name, arch)
    if os_version:
      try:
        versioned_platform = '%s_%s_%s' % (os_name, os_version, arch)
        return self._dependency_manager.FetchPath(
            binary_name, versioned_platform)
      except dependency_manager.NoPathFoundError:
        logging.warning(
            'Cannot find path for %s on platform %s. Falling back to %s.',
            binary_name, versioned_platform, platform)
    return self._dependency_manager.FetchPath(binary_name, platform)


  def LocalPath(self, binary_name, arch, os_name, os_version=None):
    """ Return a local path to the given binary name, or None if not found.

    Will not download from cloud_storage.
    """
    platform = '%s_%s' % (os_name, arch)
    if os_version:
      try:
        versioned_platform = '%s_%s_%s' % (os_name, os_version, arch)
        return self._dependency_manager.LocalPath(
            binary_name, versioned_platform)
      except dependency_manager.NoPathFoundError:
        logging.warning(
            'Cannot find local path for %s on platform %s. Falling back to %s.',
            binary_name, versioned_platform, platform)
    return self._dependency_manager.LocalPath(binary_name, platform)
