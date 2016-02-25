# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Defines common functionality used for interacting with Rietveld."""

import json
import logging
import mimetypes
import urllib

import httplib2

from google.appengine.ext import ndb

from dashboard import utils

_DESCRIPTION = """This patch was automatically uploaded by the Chrome Perf
Dashboard (https://chromeperf.appspot.com). It is being used to run a perf
bisect try job. It should not be submitted."""


class ResponseObject(object):
  """Class for Response Object.

  This class holds attributes similar to response object returned by
  google.appengine.api.urlfetch. This is used to convert response object
  returned by httplib2.Http.request.
  """

  def __init__(self, status_code, content):
    self.status_code = int(status_code)
    self.content = content


class RietveldConfig(ndb.Model):
  """Configuration info for a Rietveld service account.

  The data is stored only in the App Engine datastore (and the cloud console)
  and not the code because it contains sensitive information like private keys.
  """
  # TODO(qyearsley): Remove RietveldConfig and store the server URL in
  # datastore.
  client_email = ndb.TextProperty()
  service_account_key = ndb.TextProperty()

  # The protocol and domain of the Rietveld host. Should not contain path.
  server_url = ndb.TextProperty()

  # The protocol and domain of the Internal Rietveld host which is used
  # to create issues for internal only tests.
  internal_server_url = ndb.TextProperty()


def GetDefaultRietveldConfig():
  """Returns the default rietveld config entity from the datastore."""
  return ndb.Key(RietveldConfig, 'default_rietveld_config').get()


class RietveldService(object):
  """Implements a Python API to Rietveld via HTTP.

  Authentication is handled via an OAuth2 access token minted from an RSA key
  associated with a service account (which can be created via the Google API
  console). For this to work, the Rietveld instance to talk to must be
  configured to allow the service account client ID as OAuth2 audience (see
  Rietveld source). Both the RSA key and the server URL are provided via static
  application configuration.
  """

  def __init__(self, internal_only=False):
    self.internal_only = internal_only
    self._config = None
    self._http = None

  def Config(self):
    if not self._config:
      self._config = GetDefaultRietveldConfig()
    return self._config

  def MakeRequest(self, path, *args, **kwargs):
    """Makes a request to the Rietveld server."""
    if self.internal_only:
      server_url = self.Config().internal_server_url
    else:
      server_url = self.Config().server_url
    url = '%s/%s' % (server_url, path)
    response, content = self._Http().request(url, *args, **kwargs)
    return ResponseObject(response.get('status'), content)

  def _Http(self):
    if not self._http:
      self._http = httplib2.Http()
      credentials = utils.ServiceAccountCredentials()
      credentials.authorize(self._http)
    return self._http

  def _XsrfToken(self):
    """Requests a XSRF token from Rietveld."""
    return self.MakeRequest(
        'xsrf_token', headers={'X-Requesting-XSRF-Token': 1}).content

  def _EncodeMultipartFormData(self, fields, files):
    """Encode form fields for multipart/form-data.

    Args:
      fields: A sequence of (name, value) elements for regular form fields.
      files: A sequence of (name, filename, value) elements for data to be
             uploaded as files.
    Returns:
      (content_type, body) ready for httplib.HTTP instance.

    Source:
      http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/146306
    """
    boundary = '-M-A-G-I-C---B-O-U-N-D-A-R-Y-'
    crlf = '\r\n'
    lines = []
    for (key, value) in fields:
      lines.append('--' + boundary)
      lines.append('Content-Disposition: form-data; name="%s"' % key)
      lines.append('')
      if isinstance(value, unicode):
        value = value.encode('utf-8')
      lines.append(value)
    for (key, filename, value) in files:
      lines.append('--' + boundary)
      lines.append('Content-Disposition: form-data; name="%s"; filename="%s"' %
                   (key, filename))
      content_type = (mimetypes.guess_type(filename)[0] or
                      'application/octet-stream')
      lines.append('Content-Type: %s' % content_type)
      lines.append('')
      if isinstance(value, unicode):
        value = value.encode('utf-8')
      lines.append(value)
    lines.append('--' + boundary + '--')
    lines.append('')
    body = crlf.join(lines)
    content_type = 'multipart/form-data; boundary=%s' % boundary
    return content_type, body

  def UploadPatch(self, subject, patch, base_checksum, base_hashes,
                  base_content, config_path):
    """Uploads the given patch file contents to Rietveld.

    The process of creating an issue and uploading the patch requires several
    HTTP requests to Rietveld.

    Rietveld API documentation: https://code.google.com/p/rietveld/wiki/APIs
    For specific implementation in Rietveld codebase, see http://goo.gl/BW205J.

    Args:
      subject: Title of the job, as it will appear in rietveld.
      patch: The patch, which is a specially-formatted string.
      base_checksum: Base md5 checksum to send.
      base_hashes: "Base hashes" string to send.
      base_content: Base config file contents.
      config_path: Path to the config file.

    Returns:
      A (issue ID, patchset ID) pair. These are strings that contain numerical
      IDs. If the patch upload was unsuccessful, then (None, None) is returned.
    """
    base = 'https://chromium.googlesource.com/chromium/src.git@master'
    repo_guid = 'c14d891d44f0afff64e56ed7c9702df1d807b1ee'
    form_fields = [
        ('subject', subject),
        ('description', _DESCRIPTION),
        ('base', base),
        ('xsrf_token', self._XsrfToken()),
        ('repo_guid', repo_guid),
        ('content_upload', '1'),
        ('base_hashes', base_hashes),
    ]
    uploaded_diff_file = [('data', 'data.diff', patch)]
    ctype, body = self._EncodeMultipartFormData(
        form_fields, uploaded_diff_file)
    response = self.MakeRequest(
        'upload', method='POST', body=body, headers={'content-type': ctype})
    if response.status_code != 200:
      logging.error('Error %s uploading to /upload', response.status_code)
      logging.error(response.content)
      return (None, None)

    # There should always be 3 lines in the request, but sometimes Rietveld
    # returns 2 lines. Log the content so we can debug further.
    logging.info('Response from Rietveld /upload:\n%s', response.content)
    if not response.content.startswith('Issue created.'):
      logging.error('Unexpected response: %s', response.content)
      return (None, None)
    lines = response.content.splitlines()
    if len(lines) < 2:
      logging.error('Unexpected response %s', response.content)
      return (None, None)

    msg = lines[0]
    issue_id = msg[msg.rfind('/') + 1:]
    patchset_id = lines[1].strip()
    patches = [x.split(' ', 1) for x in lines[2:]]
    request_path = '%d/upload_content/%d/%d' % (
        int(issue_id), int(patchset_id), int(patches[0][0]))
    form_fields = [
        ('filename', config_path),
        ('status', 'M'),
        ('checksum', base_checksum),
        ('is_binary', str(False)),
        ('is_current', str(False)),
    ]
    uploaded_diff_file = [('data', config_path, base_content)]
    ctype, body = self._EncodeMultipartFormData(form_fields, uploaded_diff_file)
    response = self.MakeRequest(
        request_path, method='POST', body=body, headers={'content-type': ctype})
    if response.status_code != 200:
      logging.error(
          'Error %s uploading to %s', response.status_code, request_path)
      logging.error(response.content)
      return (None, None)

    request_path = '%s/upload_complete/%s' % (issue_id, patchset_id)
    response = self.MakeRequest(request_path, method='POST')
    if response.status_code != 200:
      logging.error(
          'Error %s uploading to %s', response.status_code, request_path)
      logging.error(response.content)
      return (None, None)
    return issue_id, patchset_id

  def TryPatch(self, tryserver_master, issue_id, patchset_id, bot):
    """Sends a request to try the given patchset on the given trybot.

    To see exactly how this request is handled, you can see the try_patchset
    handler in the Chromium branch of Rietveld: http://goo.gl/U6tJQZ

    Args:
      tryserver_master: Master name, e.g. "tryserver.chromium.perf".
      issue_id: Rietveld issue ID.
      patchset_id: Patchset ID (returned when a patch is uploaded).
      bot: Bisect bot name.

    Returns:
      True if successful, False otherwise.
    """
    args = {
        'xsrf_token': self._XsrfToken(),
        'builders': json.dumps({bot: ['defaulttests']}),
        'master': tryserver_master,
        'reason': 'Perf bisect',
        'clobber': 'False',
    }
    request_path = '%s/try/%s' % (issue_id, patchset_id)
    response = self.MakeRequest(
        request_path, method='POST', body=urllib.urlencode(args))
    if response.status_code != 200:
      logging.error(
          'Error %s POSTing to /%s/try/%s', response.status_code, issue_id,
          patchset_id)
      logging.error(response.content)
      return False
    return True
