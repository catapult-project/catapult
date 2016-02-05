#!/usr/bin/env python
"""Fetch the most recent GAE SDK and decompress it in the current directory.

Usage:
  fetch_gae_sdk.py [<dest_dir>]

Current releases are listed here:
  https://www.googleapis.com/storage/v1/b/appengine-sdks/o?prefix=featured
"""

import json
import os
import StringIO
import sys
import tempfile
import urllib2
import zipfile

_SDK_URL = (
    'https://www.googleapis.com/storage/v1/b/appengine-sdks/o?prefix=featured')

def get_gae_versions():
  try:
    version_info_json = urllib2.urlopen(_SDK_URL).read()
  except:
    return {}
  try:
    version_info = json.loads(version_info_json)
  except:
    return {}
  return version_info.get('items', {})

def _version_tuple(v):
  version_string = os.path.splitext(v['name'])[0].rpartition('_')[2]
  return tuple(int(x) for x in version_string.split('.'))

def get_sdk_urls(sdk_versions):
  python_releases = [v for v in sdk_versions
                     if v['name'].startswith('featured/google_appengine')]
  current_releases = sorted(python_releases, key=_version_tuple, reverse=True)
  return [release['mediaLink'] for release in current_releases]

def main(argv):
  if len(argv) > 2:
    print 'Usage: {} [<destination_dir>]'.format(argv[0])
    return 1
  dest_dir = argv[1] if len(argv) > 1 else '.'
  if not os.path.exists(dest_dir):
    os.makedirs(dest_dir)

  if os.path.exists(os.path.join(dest_dir, 'google_appengine')):
    print 'GAE SDK already installed at {}, exiting.'.format(dest_dir)
    return 0

  sdk_versions = get_gae_versions()
  if not sdk_versions:
    print 'Error fetching GAE SDK version info'
    return 1
  sdk_urls = get_sdk_urls(sdk_versions)
  for sdk_url in sdk_urls:
    try:
      sdk_contents = StringIO.StringIO(urllib2.urlopen(sdk_url).read())
      break
    except:
      pass
  else:
    print 'Could not read SDK from any of ', sdk_urls
    return 1
  sdk_contents.seek(0)
  try:
    zip_contents = zipfile.ZipFile(sdk_contents)
    zip_contents.extractall(dest_dir)
  except:
    print 'Error extracting SDK contents'
    return 1

if __name__ == '__main__':
  sys.exit(main(sys.argv[:]))
