# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Functions to get the desired Chrome APK.
"""
import os
import subprocess

from distutils import version  # pylint: disable=import-error,no-name-in-module
from long_term_health import utils


def DownloadAPKFromURI(uri, output_dir):
  """Used to download the APKs from google cloud into the out folder.

  Args:
    uri(string): Gsutil URI
    output_dir(string): The path that the APKs will be stored

  Returns:
    string: the path of the downloaded APK
  """

  def GetAPKName(gs_uri):
    # example `gs_uri`: gs://chrome-signed/android-B0urB0N/56.0.2924.3/arm/
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
    return version.LooseVersion(apk_name.split('_')[0])

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
    uri = milestone_info.GetLatestVersionURI(milestone_num)
    return DownloadAPKFromURI(uri, output_path)
  return local_apk_path
