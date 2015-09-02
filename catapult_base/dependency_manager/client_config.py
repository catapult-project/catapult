# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from catapult_base.dependency_manager import base_config


class ClientConfig(base_config.BaseConfig):
  def AppendToFrontOfLists(self):
    """True iff local_files from this config should override other configs.
    """
    return True

  @classmethod
  def GetConfigType(cls):
    return 'ClientConfig'

  def UpdateCloudStorageDependency(
      self, dependency_name, platform, dependency_path, version=None):
    """Update the cloud storage hash and the version for the given dependency.

    """
    raise NotImplementedError

  def GetVersion(self, dependency, platform):
    """Return the Version information for the given dependency.
    """
    raise NotImplementedError

