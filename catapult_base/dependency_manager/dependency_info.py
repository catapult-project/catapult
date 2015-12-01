# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class DependencyInfo(object):
  def __init__(self, dependency, platform, config_path, local_paths=None,
      cloud_storage_info=None):
    """ Container for the information needed for each dependency/platform pair
    in the dependency_manager.

    Args:
        Required:
          dependency: Name of the dependency.
          platform: Name of the platform to be run on.
          config_path: Path to the config_path this information came from. Used
                       for error messages to improve debugging.

        Optional:
          local_paths: A list of paths to search in order for a local file.
          cloud_storage_info: An instance of CloudStorageInfo.
    """
    # TODO(aiolos): update the above doc string for A) the usage of zip files
    # and B) supporting lists of local_paths to be checked for most recently
    # changed files.
    if not dependency or not platform:
      raise ValueError(
          'Must supply both a dependency and platform to DependencyInfo')

    self._dependency = dependency
    self._platform = platform
    self._config_paths = [config_path]
    self._local_paths = local_paths or []
    self._cloud_storage_info = cloud_storage_info

  def Update(self, new_dep_info):
    """Add the information from |new_dep_info| to this instance.
    """
    self._config_paths.extend(new_dep_info.config_paths)
    if (self.dependency != new_dep_info.dependency or
        self.platform != new_dep_info.platform):
      raise ValueError(
          'Cannot update DependencyInfo with different dependency or platform.'
          'Existing dep: %s, existing platform: %s. New dep: %s, new platform:'
          '%s. Config_paths conflicting: %s' % (
              self.dependency, self.platform, new_dep_info.dependency,
              new_dep_info.platform, self.config_paths))
    if new_dep_info.has_cloud_storage_info:
      if self.has_cloud_storage_info:
        raise ValueError(
            'Overriding cloud storage data is not allowed when updating a '
            'DependencyInfo. Conflict in dependency %s on platform %s in '
            'config_paths: %s.' % (self.dependency, self.platform,
                                  self.config_paths))
      else:
        self._cloud_storage_info = new_dep_info._cloud_storage_info
    if new_dep_info.local_paths:
      for path in new_dep_info.local_paths:
        if path not in self._local_paths:
          self._local_paths.append(path)

  def GetRemotePath(self):
    """Gets the path to a downloaded version of the dependency.

    May not download the file if it has already been downloaded.
    Will unzip the downloaded file if specified in the config
    via unzipped_hash.

    Returns: A path to an executable that was stored in cloud_storage, or None
       if not found.

    Raises:
        CredentialsError: If cloud_storage credentials aren't configured.
        PermissionError: If cloud_storage credentials are configured, but not
            with an account that has permission to download the needed file.
        NotFoundError: If the needed file does not exist where expected in
            cloud_storage or the downloaded zip file.
        ServerError: If an internal server error is hit while downloading the
            needed file.
        CloudStorageError: If another error occured while downloading the remote
            path.
        FileNotFoundError: If the download was otherwise unsuccessful.
    """
    if self.has_cloud_storage_info:
      return self._cloud_storage_info.GetRemotePath()
    return None


  @property
  def dependency(self):
    return self._dependency

  @property
  def platform(self):
    return self._platform

  @property
  def config_paths(self):
    return self._config_paths

  @property
  def local_paths(self):
    return self._local_paths

  @property
  def has_cloud_storage_info(self):
    return bool(self._cloud_storage_info)

