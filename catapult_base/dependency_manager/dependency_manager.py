# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import shutil
import stat
import tempfile
import zipfile

from catapult_base import cloud_storage
from catapult_base import support_binaries
from catapult_base.dependency_manager import base_config
from catapult_base.dependency_manager import exceptions


DEFAULT_TYPE = 'default'


class DependencyManager(object):
  def __init__(self, configs, supported_config_types=None):
    """Manages file dependencies found locally or in cloud_storage.

    Args:
        configs: A list of instances of BaseConfig or it's subclasses, passed
            in decreasing order of precedence.
        supported_config_types: A list of whitelisted config_types.
            No restrictions if None is specified.

    Raises:
        ValueError: If |configs| is not a list of instances of BaseConfig or
            its subclasses.
        UnsupportedConfigFormatError: If supported_config_types is specified and
            configs contains a config not in the supported config_types.

    Example: DependencyManager([config1, config2, config3])
        No requirements on the type of Config, and any dependencies that have
        local files for the same platform will first look in those from
        config1, then those from config2, and finally those from config3.
    """
    if configs is None or type(configs) != list:
      raise ValueError(
          'Must supply a list of config files to DependencyManager')
    # self._lookup_dict is a dictionary with the following format:
    # { dependency1: {platform1: dependency_info1,
    #                 platform2: dependency_info2}
    #   dependency2: {platform1: dependency_info3,
    #                  ...}
    #   ...}
    #
    # Where the dependencies and platforms are strings, and the
    # dependency_info's are DependencyInfo instances.
    self._lookup_dict = {}
    self.supported_configs = supported_config_types or []
    for config in configs:
      self._UpdateDependencies(config)

  def FetchPath(self, dependency, platform, try_support_binaries=False):
    """Get a path to an executable for |dependency|, downloading as needed.

    A path to a default executable may be returned if a platform specific
    version is not specified in the config(s).

    Args:
        dependency: Name of the desired dependency, as given in the config(s)
            used in this DependencyManager.
        platform: Name of the platform the dependency will run on. Often of the
            form 'os_architecture'. Must match those specified in the config(s)
            used in this DependencyManager.
        try_support_binaries: True if support_binaries should be queried if the
            dependency_manager was not initialized with data for |dependency|.

    Returns:
        A path to an executable of |dependency| that will run on |platform|,
        downloading from cloud storage if needed.

    Raises:
        NoPathFoundError: If a local copy of the executable cannot be found and
            a remote path could not be downloaded from cloud_storage.
        CredentialsError: If cloud_storage credentials aren't configured.
        PermissionError: If cloud_storage credentials are configured, but not
            with an account that has permission to download the remote file.
        NotFoundError: If the remote file does not exist where expected in
            cloud_storage.
        ServerError: If an internal server error is hit while downloading the
            remote file.
        CloudStorageError: If another error occured while downloading the remote
            path.
        FileNotFoundError: If an attempted download was otherwise unsuccessful.

    """
    dependency_info = self._GetDependencyInfo(dependency, platform)
    if not dependency_info:
      if not try_support_binaries:
        raise exceptions.NoPathFoundError(dependency, platform)
      # TODO(aiolos): Remove the support_binaries call and always raise
      # NoPathFound once the binary dependencies are moved over to the new
      # system.

      # platform should be of the form '%s_%s' % (os_name, arch_name) when
      # called from the binary_manager.
      platform_parts = platform.split('_', 1)
      assert len(platform_parts) == 2
      platform_os, platform_arch = platform_parts
      logging.info('Calling into support_binaries with dependency %s, platform '
                   '%s and arch %s. support_binaries is deprecated.'
                   % (dependency, platform_os, platform_arch))
      return support_binaries.FindPath(dependency, platform_arch,
                                       platform_os)
    path = self._LocalPath(dependency_info)
    if not path or not os.path.exists(path):
      path = self._CloudStoragePath(dependency_info)
      if not path or not os.path.exists(path):
        raise exceptions.NoPathFoundError(dependency, platform)
    return path

  def LocalPath(self, dependency, platform, try_support_binaries=False):
    """Get a path to a locally stored executable for |dependency|.

    A path to a default executable may be returned if a platform specific
    version is not specified in the config(s).
    Will not download the executable.

    Args:
        dependency: Name of the desired dependency, as given in the config(s)
            used in this DependencyManager.
        platform: Name of the platform the dependency will run on. Often of the
            form 'os_architecture'. Must match those specified in the config(s)
            used in this DependencyManager.
        try_support_binaries: True if support_binaries should be queried if the
            dependency_manager was not initialized with data for |dependency|.

    Returns:
        A path to an executable for |dependency| that will run on |platform|.

    Raises:
        NoPathFoundError: If a local copy of the executable cannot be found.
    """
    # TODO(aiolos): Remove the support_binaries call and always raise
    # NoPathFound once the binary dependencies are moved over to the new
    # system.
    dependency_info = self._GetDependencyInfo(dependency, platform)
    if not dependency_info:
      if not try_support_binaries:
        raise exceptions.NoPathFoundError(dependency, platform)
      return support_binaries.FindLocallyBuiltPath(dependency)
    local_path = self._LocalPath(dependency_info)
    if not local_path or not os.path.exists(local_path):
      raise exceptions.NoPathFoundError(dependency, platform)
    return local_path

  def _UpdateDependencies(self, config):
    """Add the dependency information stored in |config| to this instance.

    Args:
        config: An instances of BaseConfig or a subclasses.

    Raises:
        UnsupportedConfigFormatError: If supported_config_types was specified
        and config is not in the supported config_types.
    """
    if not isinstance(config, base_config.BaseConfig):
      raise ValueError('Must use a BaseConfig or subclass instance with the '
                       'DependencyManager.')
    if (self.supported_configs and
        config.GetConfigType() not in self.supported_configs):
      raise exceptions.UnsupportedConfigFormatError(config.GetConfigType(),
                                                    config.config_path)
    for dep_info in config.IterDependencyInfo():
      dependency = dep_info.dependency
      platform = dep_info.platform
      if dependency not in self._lookup_dict:
        self._lookup_dict[dependency] = {}
      if platform not in self._lookup_dict[dependency]:
        self._lookup_dict[dependency][platform] = dep_info
      else:
        self._lookup_dict[dependency][platform].Update(dep_info)


  def _GetDependencyInfo(self, dependency, platform):
    """Get information for |dependency| on |platform|, or a default if needed.

    Args:
        dependency: Name of the desired dependency, as given in the config(s)
            used in this DependencyManager.
        platform: Name of the platform the dependency will run on. Often of the
            form 'os_architecture'. Must match those specified in the config(s)
            used in this DependencyManager.

    Returns: The dependency_info for |dependency| on |platform| if it exists.
        Or the default version of |dependency| if it exists, or None if neither
        exist.
    """
    if not self._lookup_dict or dependency not in self._lookup_dict:
      return None
    dependency_dict = self._lookup_dict[dependency]
    device_type = platform
    if not device_type in dependency_dict:
      device_type = DEFAULT_TYPE
    return dependency_dict.get(device_type)

  @staticmethod
  def _LocalPath(dependency_info):
    """Return a path to a locally stored file for |dependency_info|.

    Will not download the file.

    Args:
        dependency_info: A DependencyInfo instance for the dependency to be
            found and the platform it should run on.

    Returns: A path to a local file, or None if not found.
    """
    if dependency_info:
      paths = dependency_info.local_paths
      for local_path in paths:
        if os.path.exists(local_path):
          return local_path
    return None

  @staticmethod
  def _CloudStoragePath(dependency_info):
    """Return a path to a downloaded file for |dependency_info|.

    May not download the file if it has already been downloaded.

    Args:
        dependency_info: A DependencyInfo instance for the dependency to be
            found and the platform it should run on.

    Returns: A path to an executable that was stored in cloud_storage, or None
       if not found.

    Raises:
        CredentialsError: If cloud_storage credentials aren't configured.
        PermissionError: If cloud_storage credentials are configured, but not
            with an account that has permission to download the needed file.
        NotFoundError: If the needed file does not exist where expected in
            cloud_storage.
        ServerError: If an internal server error is hit while downloading the
            needed file.
        CloudStorageError: If another error occured while downloading the remote
            path.
        FileNotFoundError: If the download was otherwise unsuccessful.
    """
    if not dependency_info:
      return None
    cs_path = dependency_info.cs_remote_path
    cs_hash = dependency_info.cs_hash
    cs_bucket = dependency_info.cs_bucket
    download_path = dependency_info.download_path
    if not cs_path or not cs_bucket or not cs_hash or not download_path:
      return None

    download_dir = os.path.dirname(download_path)
    if not os.path.exists(download_dir):
      os.makedirs(download_dir)

    cloud_storage.GetIfHashChanged(cs_path, download_path, cs_bucket, cs_hash)
    if not os.path.exists(download_path):
      raise exceptions.FileNotFoundError(download_path)

    # TODO(aiolos): Add tests once the refactor is completed. crbug.com/551158
    unzip_location = dependency_info.unzip_location
    if unzip_location:
      download_path = DependencyManager._UnzipFile(
          download_path, unzip_location, dependency_info.path_within_archive)

    os.chmod(download_path,
             stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IRGRP)
    return os.path.abspath(download_path)


  @staticmethod
  def _UnzipFile(archive_file, unzip_location, path_within_archive):
    """Unzips a file if it is a zip file.

    Args:
        archive_file: The downloaded file to unzip.
        unzip_location: The destination directory to unzip to.
        path_within_archive: The relative location of the dependency
            within the unzipped archive.

    Returns:
        The path to the unzipped dependency.

    Raises:
        ValueError: If |archive_file| is not a zipfile.
        ArchiveError: If the dependency cannot be found in the unzipped
            location.
    """
    # TODO(aiolos): Add tests once the refactor is completed. crbug.com/551158
    if not zipfile.is_zipfile(archive_file):
      raise ValueError(
          'Attempting to unzip a non-archive file at %s' % archive_file)
    tmp_location = None
    if os.path.exists(unzip_location):
      os_tmp_dir = '%stmp' % os.sep
      tmp_location = tempfile.mkdtemp(dir=os_tmp_dir)
      shutil.move(unzip_location, tmp_location)
    try:
      with zipfile.ZipFile(archive_file, 'r') as archive:
        for content in archive.namelist():
          # Ensure all contents in zip file are extracted into the
          # unzip_location. zipfile.extractall() is a security risk, and should
          # not be used without prior verification that the python verion
          # being used is at least 2.7.4
          dest = os.path.join(unzip_location,
                              content[content.find(os.path.sep)+1:])
          if not os.path.isdir(os.path.dirname(dest)):
            os.makedirs(os.path.dirname(dest))
          if not os.path.basename(dest):
            continue
          with archive.open(content) as unzipped_content:
            logging.debug(
                'Extracting %s to %s (%s)', content, dest, archive_file)
            with file(dest, 'wb') as dest_file:
              dest_file.write(unzipped_content.read())
            permissions = archive.getinfo(content).external_attr >> 16
            if permissions:
              os.chmod(dest, permissions)
      download_path = os.path.join(unzip_location, path_within_archive)
      if not download_path:
        raise exceptions.ArchiveError('Expected path %s was not extracted from '
                                      'the downloaded archive.', download_path)
    except:
      if tmp_location:
        shutil.move(tmp_location, unzip_location)
      raise
    if tmp_location:
      shutil.rmtree(tmp_location)
    return download_path

