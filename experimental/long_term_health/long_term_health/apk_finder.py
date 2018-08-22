# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Functions to get the desired Chrome APK.
"""
from collections import namedtuple
import os
import subprocess

from long_term_health import utils


PROCESSOR_ARCHITECTURE = 'arm'


class ChromeVersion(namedtuple('Version', 'milestone minor build patch')):
  """Class to represents chrome version number.
  """

  def __new__(cls, *args):
    """Create a new instance of ChromeVersion.

    It accepts either one argument(a string, e.g. '64.0.3325.45') or four
    arguments(4 integers, (64, 0, 3325, 45)) and create a new instance of
    ChromeVersion.

    Args:
      *args: arguments, either one or four

    Returns:
      ChromeVersion: new ChromeVersion instance

    """
    assert len(args) == 1 or len(args) == 4, 'Wrong argument numbers.'
    if len(args) == 1:
      args = [int(v) for v in args[0].split('.')]
    return super(ChromeVersion, cls).__new__(cls, *args)

  def __str__(self):
    return '.'.join([str(n) for n in self])

  def GetDecrementedVersionNum(self, num):
    """Get the version number with patch number decremented by given amount.

    ChromeVersion('68.0.3440.70').getDecrementedVersionNum(6) => '68.0.3440.64'

    Args:
      num(int): the amount that the patch number need to be reduced

    Returns:
      ChromeVersion: decremented Chrome version
    """
    patch_num = self.patch - num
    assert patch_num >= 0, 'patch number cannot be negative'
    return type(self)(self.milestone, self.minor, self.build, patch_num)


def GetLatestAvailableVersionURI(version_num):
  """Get the latest available google cloud storage URI for given version.

  If the URI for the given version number is not available, it will decrement
  the version number and try to find the latest available one.

  Args:
    version_num(string): String representing the latest version number.

  Returns:
    string: The URI for the latest version of Chrome for a given milestone.

  Raises:
    CloudDownloadFailed: this would be risen if we cannot find the apk within
    5 patches
  """

  chrome_version = ChromeVersion(version_num)
  # Monochrome is introduced at M53, we will use normal chrome for earlier
  # milestones
  chrome_type = 'Monochrome' if chrome_version.milestone >= 53 else 'Chrome'
  # check whether the latest patch is in the Google Cloud storage as
  # sometimes it is not, so we need to decrement patch and get the
  # previous one
  for i in range(20):
    # above number has been tested, and it works from milestone 45 to 68
    download_uri = ('gs://chrome-signed/android-*/%s/%s/%s'
                    'Stable.apk') % (chrome_version.GetDecrementedVersionNum(i),
                                     PROCESSOR_ARCHITECTURE, chrome_type)
    # check exit code to confirm the existence of the package
    if subprocess.call(['gsutil', 'ls', download_uri]) == 0:
      return download_uri

  raise utils.CloudDownloadFailed(version_num)


def DownloadAPKFromURI(uri, output_dir):
  """Used to download the APKs from google cloud into the out folder.

  Args:
    uri(string): Gsutil URI
    output_dir(string): The path that the APKs will be stored

  Returns:
    string: the path of the downloaded APK
  """

  def GetAPKName(gs_uri):
    # example `gs_uri`: gs://chrome-signed/android-*/56.0.2924.3/arm/
    # ChromeStable.apk
    return '_'.join(gs_uri.split('/')[-3:])

  path_to_apk = os.path.join(output_dir, GetAPKName(uri))

  try:
    subprocess.check_call(['gsutil', 'cp', uri, path_to_apk])
  except subprocess.CalledProcessError:
    raise utils.CloudDownloadFailed(uri)

  return path_to_apk


def GetLocalAPK(milestone_num, output_path):
  """Get the local path of the APK for the given milestone.

  Args:
    milestone_num(int): the milestone number
    output_path(string): the directory that the apks will be downloaded in

  Returns:
    string/None: returns None if there is no local apk, returns path otherwise
  """
  def ParseVersion(apk_name):
    return ChromeVersion(apk_name.split('_')[0])

  if not os.path.isdir(output_path):
    return None

  local_apks = sorted([apk for apk in os.listdir(
      output_path) if apk.startswith('%d.' % milestone_num)], key=ParseVersion)
  return None if not local_apks else os.path.join(output_path, local_apks[-1])


def GetAPK(milestone_num, output_path, milestone_info):
  """Get the path to an APK, download if it doesn't exist.

  Args:
    milestone_num(int): milestone number
    output_path(string): the directory that the apks will be downloaded in
    milestone_info(MilestoneInfo):

  Returns:
    string: the path to the apk for the given milestone
  """
  local_apk_path = GetLocalAPK(milestone_num, output_path)
  if local_apk_path is None:
    uri = GetLatestAvailableVersionURI(
        milestone_info.GetVersionNumberFromMilestone(milestone_num))
    return DownloadAPKFromURI(uri, output_path)
  return local_apk_path
