# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Bootstrap Chrome Telemetry by downloading all its files from SVN servers.

Requires a DEPS file to specify which directories on which SVN servers
are required to run Telemetry. Format of that DEPS file is a subset of the
normal DEPS file format[1]; currently only only the "deps" dictionary is
supported and nothing else.

Fetches all files in the specified directories using WebDAV (SVN is WebDAV under
the hood).

[1] http://dev.chromium.org/developers/how-tos/depottools#TOC-DEPS-file
"""

import imp
import logging
import os
import urllib
import urlparse

# Link to file containing the 'davclient' WebDAV client library.
# TODO(wiltzius): Change this to point at Chromium SVN server after checkin.
_DAVCLIENT_URL = ('http://svn.osafoundation.org/tools/davclient/trunk/src/'
                  'davclient/davclient.py')

# Dummy module for Davclient.
_davclient = None

def _download_and_import_davclient_module():
  """Dynamically import davclient helper library."""
  global _davclient
  davclient_src = urllib.urlopen(_DAVCLIENT_URL).read()
  _davclient = imp.new_module('davclient')
  exec davclient_src in _davclient.__dict__


class DAVClientWrapper():
  """Knows how to retrieve subdirectories and files from WebDAV/SVN servers."""

  def __init__(self, root_url):
    """Initialize SVN server root_url, save files to local dest_dir.

    Args:
      root_url: string url of SVN/WebDAV server
    """
    self.root_url = root_url
    self.client = _davclient.DAVClient(root_url)

  def GetSubdirs(self, path):
    """Returns string names of all subdirs of this path on the SVN server."""
    props = self.client.propfind(path, depth=1)
    return map(os.path.basename, props.keys())

  def IsFile(self, path):
    """Returns True if the path is a file on the server, False if directory."""
    props = self.client.propfind(path, depth=1)
    # Build up normalized path list since paths to directories may or may not
    # have trailing slashes.
    norm_keys = {}
    for entry in props.keys():
      norm_keys[os.path.normpath(entry)] = entry
    return props[norm_keys[os.path.normpath(path)]]['resourcetype'] is None

  def Traverse(self, src_path, dst_path):
    """Walks the directory hierarchy pointed to by src_path download all files.

    Recursively walks src_path and saves all files and subfolders into
    dst_path.

    Args:
      src_path: string path on SVN server to save (absolute path on server).
      dest_path: string local path (relative or absolute) to save to.
    """
    if self.IsFile(src_path):
      if not os.path.exists(os.path.dirname(dst_path)):
        logging.info("creating %s", os.path.dirname(dst_path))
        os.makedirs(os.path.dirname(dst_path))
      logging.info("Saving %s to %s", self.root_url + src_path, dst_path)
      urllib.urlretrieve(self.root_url + src_path, dst_path)
      return
    else:
      for subdir in self.GetSubdirs(src_path):
        if subdir:
          self.Traverse(os.path.join(src_path, subdir),
                        os.path.join(dst_path, subdir))


def DownloadDEPS(destination_dir, deps_path='DEPS'):
  """Saves all the dependencies in deps_path.

  Reads the file at deps_path, assuming this file in the standard gclient DEPS
  format, and then download all files/directories listed in that DEPS file to
  the destination_dir.

  Args:
    deps_path: String path to DEPS file. Defaults to ./DEPS.
    destination_dir: String path to directory to download files into.
  """
  # TODO(wiltzius): Add a parameter for which revision to pull.
  _download_and_import_davclient_module()

  with open(deps_path) as deps_file:
    deps_content = deps_file.read()

  deps = imp.new_module('deps')
  exec deps_content in deps.__dict__

  for dst_path, src_path in deps.deps.iteritems():
    full_dst_path = os.path.join(destination_dir, dst_path)
    parsed_url = urlparse.urlparse(src_path)
    root_url = parsed_url.scheme + '://' + parsed_url.netloc

    dav_client = DAVClientWrapper(root_url)
    dav_client.Traverse(parsed_url.path, full_dst_path)

    # Recursively fetch any DEPS defined in a subdirectory we just fetched.
    for dirpath, _dirnames, filenames in os.walk(full_dst_path):
      if 'DEPS' in filenames:
        DownloadDEPS(os.path.join(dirpath, 'DEPS'), destination_dir)

