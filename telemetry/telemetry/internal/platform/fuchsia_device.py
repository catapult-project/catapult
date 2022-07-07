# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A Fuchsia device instance"""

from __future__ import absolute_import
import json
import logging
import os
import platform
import posixpath
import subprocess
import tarfile

from telemetry.core import fuchsia_interface
from telemetry.core import util
from telemetry.internal.platform import device

_LIST_DEVICES_TIMEOUT_SECS = 5
_GCS_PREFIX = 'gs://fuchsia/sdk/core/linux-amd64'
_GSUTIL_PATH = os.path.join(
    util.GetCatapultDir(), 'third_party', 'gsutil', 'gsutil')


class FuchsiaDevice(device.Device):

  def __init__(self, host, ssh_config, system_log_file,
               port, target_id, managed_repo):
    super().__init__(
        name='Fuchsia with host: %s' % host,
        guid=host)
    self._ssh_config = ssh_config
    self._system_log_file = system_log_file
    self._host = host
    self._port = port
    self._target_id = target_id
    self._managed_repo = managed_repo

  @classmethod
  def GetAllConnectedDevices(cls, denylist):
    return []

  @property
  def managed_repo(self):
    return self._managed_repo

  @property
  def host(self):
    return self._host

  @property
  def ssh_config(self):
    return self._ssh_config

  @property
  def system_log_file(self):
    return self._system_log_file

  @property
  def port(self):
    return self._port

  @property
  def target_id(self):
    return self._target_id


def _GetLatestSDKHash():
  gcs_archive = posixpath.join(_GCS_PREFIX, 'LATEST_ARCHIVE')
  archive_cmd = [_GSUTIL_PATH, 'cat', gcs_archive]
  return subprocess.check_output(archive_cmd,
                                 stderr=subprocess.STDOUT).decode('utf-8')


def _DownloadFuchsiaSDK(tar_file, dest=fuchsia_interface.SDK_ROOT):
  if not os.path.isdir(dest):
    os.makedirs(dest)
  gcs_sdk = posixpath.join(_GCS_PREFIX, _GetLatestSDKHash())
  download_cmd = [_GSUTIL_PATH, 'cp', gcs_sdk, tar_file]
  subprocess.check_output(download_cmd, stderr=subprocess.STDOUT)

  with tarfile.open(tar_file, 'r') as tar:
    # tarfile only accepts POSIX paths.
    tar.extractall(dest)
  os.remove(tar_file)


def _FindFuchsiaDevice():
  """Returns the (possibly empty) list of targets known to ffx."""

  json_targets = fuchsia_interface.run_ffx_command(
      ['target', 'list', '-f', 'json'],
      capture_output=True).stdout.strip()
  if not json_targets:
    return []
  return json.loads(json_targets)


def _DownloadFuchsiaSDKIfNecessary():
  """Downloads the Fuchsia SDK if not found in Chromium and Catapult repo.

  Returns:
    The path to the Fuchsia SDK directory
  """
  if not os.path.exists(fuchsia_interface.SDK_ROOT):
    tar_file = os.path.join(fuchsia_interface.SDK_ROOT, 'fuchsia-sdk.tar')
    _DownloadFuchsiaSDK(tar_file)


def _get_ssh_address(target_id):
  """Get the ssh address for the Fuchsia target."""

  ssh_address = fuchsia_interface.run_ffx_command(
      ['target', 'get-ssh-address'],
      target_id,
      capture_output=True).stdout.strip()

  def parse_host_port(host_port_pair):
    """Parses a host name or IP address and a port number from a string of any
    of the following forms:
    - hostname:port
    - IPv4addy:port
    - [IPv6addy]:port

    Returns:
      A tuple of the string host name/address and integer port number.

    Raises:
      ValueError if `host_port_pair` does not contain a colon or if the
      substring following the last colon cannot be converted to an int.
    """

    host, port = host_port_pair.rsplit(':', 1)

    # Strip the brackets if the host looks like an IPv6 address.
    if len(host) > 2 and host[0] == '[' and host[-1] == ']':
      host = host[1:-1]
    return (host, int(port))

  return parse_host_port(ssh_address)


def FindAllAvailableDevices(options):
  """Returns a list of available device types."""

  # Will not find Fuchsia devices if Fuchsia browser is not specified.
  # This means that unless specifying browser=web-engine-shell, the user
  # will not see web-engine-shell as an available browser.
  if options.browser_type not in fuchsia_interface.FUCHSIA_BROWSERS:
    return []

  if (platform.system() != 'Linux' or (
      platform.machine() != 'x86_64' and platform.machine() != 'aarch64')):
    logging.warning(
        'Fuchsia in Telemetry only supports Linux x64 or arm64 hosts.')
    return []

  # If the ssh port of the device has been forwarded to a port on the host,
  # return that device directly.
  if options.fuchsia_ssh_port:
    return [FuchsiaDevice(host='localhost',
                          system_log_file=options.fuchsia_system_log_file,
                          ssh_config=options.fuchsia_ssh_config,
                          port=options.fuchsia_ssh_port,
                          target_id=options.fuchsia_target_id,
                          managed_repo=options.fuchsia_repo)]

  # If the IP address of the device is specified, use that directly.
  if options.fuchsia_device_address:
    return [FuchsiaDevice(host=options.fuchsia_device_address,
                          system_log_file=options.fuchsia_system_log_file,
                          ssh_config=options.fuchsia_ssh_config,
                          port=options.fuchsia_ssh_port,
                          target_id=options.fuchsia_target_id,
                          managed_repo=options.fuchsia_repo)]

  if options.fuchsia_target_id:
    host, port = _get_ssh_address(options.fuchsia_target_id)
    return [FuchsiaDevice(host=host,
                          system_log_file=options.fuchsia_system_log_file,
                          ssh_config=options.fuchsia_ssh_config,
                          port=port,
                          target_id=options.fuchsia_target_id,
                          managed_repo=options.fuchsia_repo)]

  # Download the Fuchsia SDK if it doesn't exist.
  # TODO(https://crbug.com/1031763): Figure out how to use the dependency
  # manager.
  _DownloadFuchsiaSDKIfNecessary()

  try:
    device_list = _FindFuchsiaDevice()
  except OSError:
    logging.error('Fuchsia SDK Download failed. Please remove '
                  '%s and try again.', fuchsia_interface.SDK_ROOT)
    raise
  if not device_list:
    return []
  host = device_list[0].get('addresses')[0]
  target_id = device_list[0].get('nodename')
  logging.info('Using Fuchsia device with address %s and name %s'
               % (host, target_id))
  return [FuchsiaDevice(host=host,
                        system_log_file=options.fuchsia_system_log_file,
                        ssh_config=options.fuchsia_ssh_config,
                        port=options.fuchsia_ssh_port,
                        target_id=target_id,
                        managed_repo=options.fuchsia_repo)]
