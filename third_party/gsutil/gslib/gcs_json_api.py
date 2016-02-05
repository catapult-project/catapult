# -*- coding: utf-8 -*-
# Copyright 2014 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""JSON gsutil Cloud API implementation for Google Cloud Storage."""

from __future__ import absolute_import

import httplib
import json
import logging
import os
import socket
import ssl
import time
import traceback

from apitools.base.py import credentials_lib
from apitools.base.py import encoding
from apitools.base.py import exceptions as apitools_exceptions
from apitools.base.py import http_wrapper as apitools_http_wrapper
from apitools.base.py import transfer as apitools_transfer
from apitools.base.py.util import CalculateWaitForRetry

import boto
from boto import config
from gcs_oauth2_boto_plugin import oauth2_helper
import httplib2
import oauth2client
from oauth2client import devshell
from oauth2client import multistore_file

from gslib.cloud_api import AccessDeniedException
from gslib.cloud_api import ArgumentException
from gslib.cloud_api import BadRequestException
from gslib.cloud_api import CloudApi
from gslib.cloud_api import NotEmptyException
from gslib.cloud_api import NotFoundException
from gslib.cloud_api import PreconditionException
from gslib.cloud_api import Preconditions
from gslib.cloud_api import ResumableDownloadException
from gslib.cloud_api import ResumableUploadAbortException
from gslib.cloud_api import ResumableUploadException
from gslib.cloud_api import ResumableUploadStartOverException
from gslib.cloud_api import ServiceException
from gslib.cloud_api_helper import ValidateDstObjectMetadata
from gslib.cred_types import CredTypes
from gslib.exception import CommandException
from gslib.gcs_json_media import BytesTransferredContainer
from gslib.gcs_json_media import DownloadCallbackConnectionClassFactory
from gslib.gcs_json_media import HttpWithDownloadStream
from gslib.gcs_json_media import HttpWithNoRetries
from gslib.gcs_json_media import UploadCallbackConnectionClassFactory
from gslib.gcs_json_media import WrapDownloadHttpRequest
from gslib.gcs_json_media import WrapUploadHttpRequest
from gslib.no_op_credentials import NoOpCredentials
from gslib.progress_callback import ProgressCallbackWithBackoff
from gslib.project_id import PopulateProjectId
from gslib.third_party.storage_apitools import storage_v1_client as apitools_client
from gslib.third_party.storage_apitools import storage_v1_messages as apitools_messages
from gslib.tracker_file import DeleteTrackerFile
from gslib.tracker_file import GetRewriteTrackerFilePath
from gslib.tracker_file import HashRewriteParameters
from gslib.tracker_file import ReadRewriteTrackerFile
from gslib.tracker_file import WriteRewriteTrackerFile
from gslib.translation_helper import CreateBucketNotFoundException
from gslib.translation_helper import CreateNotFoundExceptionForObjectWrite
from gslib.translation_helper import CreateObjectNotFoundException
from gslib.translation_helper import DEFAULT_CONTENT_TYPE
from gslib.translation_helper import PRIVATE_DEFAULT_OBJ_ACL
from gslib.translation_helper import REMOVE_CORS_CONFIG
from gslib.util import GetBotoConfigFileList
from gslib.util import GetCertsFile
from gslib.util import GetCredentialStoreFilename
from gslib.util import GetGceCredentialCacheFilename
from gslib.util import GetJsonResumableChunkSize
from gslib.util import GetMaxRetryDelay
from gslib.util import GetNewHttp
from gslib.util import GetNumRetries
from gslib.util import UTF8


# Implementation supports only 'gs' URLs, so provider is unused.
# pylint: disable=unused-argument

DEFAULT_GCS_JSON_VERSION = 'v1'

NUM_BUCKETS_PER_LIST_PAGE = 1000
NUM_OBJECTS_PER_LIST_PAGE = 1000

TRANSLATABLE_APITOOLS_EXCEPTIONS = (apitools_exceptions.HttpError,
                                    apitools_exceptions.StreamExhausted,
                                    apitools_exceptions.TransferError,
                                    apitools_exceptions.TransferInvalidError)

# TODO: Distribute these exceptions better through apitools and here.
# Right now, apitools is configured not to handle any exceptions on
# uploads/downloads.
# oauth2_client tries to JSON-decode the response, which can result
# in a ValueError if the response was invalid. Until that is fixed in
# oauth2_client, need to handle it here.
HTTP_TRANSFER_EXCEPTIONS = (apitools_exceptions.TransferRetryError,
                            apitools_exceptions.BadStatusCodeError,
                            # TODO: Honor retry-after headers.
                            apitools_exceptions.RetryAfterError,
                            apitools_exceptions.RequestError,
                            httplib.BadStatusLine,
                            httplib.IncompleteRead,
                            httplib.ResponseNotReady,
                            httplib2.ServerNotFoundError,
                            socket.error,
                            socket.gaierror,
                            socket.timeout,
                            ssl.SSLError,
                            ValueError)

_VALIDATE_CERTIFICATES_503_MESSAGE = (
    """Service Unavailable. If you have recently changed
    https_validate_certificates from True to False in your boto configuration
    file, please delete any cached access tokens in your filesystem (at %s)
    and try again.""" % GetCredentialStoreFilename())


class GcsJsonApi(CloudApi):
  """Google Cloud Storage JSON implementation of gsutil Cloud API."""

  def __init__(self, bucket_storage_uri_class, logger, provider=None,
               credentials=None, debug=0, trace_token=None):
    """Performs necessary setup for interacting with Google Cloud Storage.

    Args:
      bucket_storage_uri_class: Unused.
      logger: logging.logger for outputting log messages.
      provider: Unused.  This implementation supports only Google Cloud Storage.
      credentials: Credentials to be used for interacting with Google Cloud
                   Storage.
      debug: Debug level for the API implementation (0..3).
      trace_token: Trace token to pass to the API implementation.
    """
    # TODO: Plumb host_header for perfdiag / test_perfdiag.
    # TODO: Add jitter to apitools' http_wrapper retry mechanism.
    super(GcsJsonApi, self).__init__(bucket_storage_uri_class, logger,
                                     provider='gs', debug=debug)
    no_op_credentials = False
    if not credentials:
      loaded_credentials = self._CheckAndGetCredentials(logger)

      if not loaded_credentials:
        loaded_credentials = NoOpCredentials()
        no_op_credentials = True
    else:
      if isinstance(credentials, NoOpCredentials):
        no_op_credentials = True

    self.credentials = credentials or loaded_credentials

    self.certs_file = GetCertsFile()

    self.http = GetNewHttp()

    # Re-use download and upload connections. This class is only called
    # sequentially, but we can share TCP warmed-up connections across calls.
    self.download_http = self._GetNewDownloadHttp()
    self.upload_http = self._GetNewUploadHttp()
    if self.credentials:
      self.authorized_download_http = self.credentials.authorize(
          self.download_http)
      self.authorized_upload_http = self.credentials.authorize(self.upload_http)
    else:
      self.authorized_download_http = self.download_http
      self.authorized_upload_http = self.upload_http

    WrapDownloadHttpRequest(self.authorized_download_http)
    WrapUploadHttpRequest(self.authorized_upload_http)

    self.http_base = 'https://'
    gs_json_host = config.get('Credentials', 'gs_json_host', None)
    self.host_base = gs_json_host or 'www.googleapis.com'

    if not gs_json_host:
      gs_host = config.get('Credentials', 'gs_host', None)
      if gs_host:
        raise ArgumentException(
            'JSON API is selected but gs_json_host is not configured, '
            'while gs_host is configured to %s. Please also configure '
            'gs_json_host and gs_json_port to match your desired endpoint.'
            % gs_host)

    gs_json_port = config.get('Credentials', 'gs_json_port', None)

    if not gs_json_port:
      gs_port = config.get('Credentials', 'gs_port', None)
      if gs_port:
        raise ArgumentException(
            'JSON API is selected but gs_json_port is not configured, '
            'while gs_port is configured to %s. Please also configure '
            'gs_json_host and gs_json_port to match your desired endpoint.'
            % gs_port)
      self.host_port = ''
    else:
      self.host_port = ':' + config.get('Credentials', 'gs_json_port')

    self.api_version = config.get('GSUtil', 'json_api_version',
                                  DEFAULT_GCS_JSON_VERSION)
    self.url_base = (self.http_base + self.host_base + self.host_port + '/' +
                     'storage/' + self.api_version + '/')

    credential_store_key_dict = self._GetCredentialStoreKeyDict(
        self.credentials)

    self.credentials.set_store(
        multistore_file.get_credential_storage_custom_key(
            GetCredentialStoreFilename(), credential_store_key_dict))

    self.num_retries = GetNumRetries()
    self.max_retry_wait = GetMaxRetryDelay()

    log_request = (debug >= 3)
    log_response = (debug >= 3)

    self.global_params = apitools_messages.StandardQueryParameters(
        trace='token:%s' % trace_token) if trace_token else None

    self.api_client = apitools_client.StorageV1(
        url=self.url_base, http=self.http, log_request=log_request,
        log_response=log_response, credentials=self.credentials,
        version=self.api_version, default_global_params=self.global_params)
    self.api_client.max_retry_wait = self.max_retry_wait
    self.api_client.num_retries = self.num_retries

    if no_op_credentials:
      # This API key is not secret and is used to identify gsutil during
      # anonymous requests.
      self.api_client.AddGlobalParam('key',
                                     u'AIzaSyDnacJHrKma0048b13sh8cgxNUwulubmJM')

  def _CheckAndGetCredentials(self, logger):
    configured_cred_types = []
    try:
      if self._HasOauth2UserAccountCreds():
        configured_cred_types.append(CredTypes.OAUTH2_USER_ACCOUNT)
      if self._HasOauth2ServiceAccountCreds():
        configured_cred_types.append(CredTypes.OAUTH2_SERVICE_ACCOUNT)
      if len(configured_cred_types) > 1:
        # We only allow one set of configured credentials. Otherwise, we're
        # choosing one arbitrarily, which can be very confusing to the user
        # (e.g., if only one is authorized to perform some action) and can
        # also mask errors.
        # Because boto merges config files, GCE credentials show up by default
        # for GCE VMs. We don't want to fail when a user creates a boto file
        # with their own credentials, so in this case we'll use the OAuth2
        # user credentials.
        failed_cred_type = None
        raise CommandException(
            ('You have multiple types of configured credentials (%s), which is '
             'not supported. One common way this happens is if you run gsutil '
             'config to create credentials and later run gcloud auth, and '
             'create a second set of credentials. Your boto config path is: '
             '%s. For more help, see "gsutil help creds".')
            % (configured_cred_types, GetBotoConfigFileList()))

      failed_cred_type = CredTypes.OAUTH2_USER_ACCOUNT
      user_creds = self._GetOauth2UserAccountCreds()
      failed_cred_type = CredTypes.OAUTH2_SERVICE_ACCOUNT
      service_account_creds = self._GetOauth2ServiceAccountCreds()
      failed_cred_type = CredTypes.GCE
      gce_creds = self._GetGceCreds()
      failed_cred_type = CredTypes.DEVSHELL
      devshell_creds = self._GetDevshellCreds()
      return user_creds or service_account_creds or gce_creds or devshell_creds
    except:  # pylint: disable=bare-except

      # If we didn't actually try to authenticate because there were multiple
      # types of configured credentials, don't emit this warning.
      if failed_cred_type:
        if os.environ.get('CLOUDSDK_WRAPPER') == '1':
          logger.warn(
              'Your "%s" credentials are invalid. Please run\n'
              '  $ gcloud auth login', failed_cred_type)
        else:
          logger.warn(
              'Your "%s" credentials are invalid. For more help, see '
              '"gsutil help creds", or re-run the gsutil config command (see '
              '"gsutil help config").', failed_cred_type)

      # If there's any set of configured credentials, we'll fail if they're
      # invalid, rather than silently falling back to anonymous config (as
      # boto does). That approach leads to much confusion if users don't
      # realize their credentials are invalid.
      raise

  def _HasOauth2ServiceAccountCreds(self):
    return config.has_option('Credentials', 'gs_service_key_file')

  def _HasOauth2UserAccountCreds(self):
    return config.has_option('Credentials', 'gs_oauth2_refresh_token')

  def _HasGceCreds(self):
    return config.has_option('GoogleCompute', 'service_account')

  def _GetOauth2ServiceAccountCreds(self):
    if self._HasOauth2ServiceAccountCreds():
      return oauth2_helper.OAuth2ClientFromBotoConfig(
          boto.config,
          cred_type=CredTypes.OAUTH2_SERVICE_ACCOUNT).GetCredentials()

  def _GetOauth2UserAccountCreds(self):
    if self._HasOauth2UserAccountCreds():
      return oauth2_helper.OAuth2ClientFromBotoConfig(
          boto.config).GetCredentials()

  def _GetGceCreds(self):
    if self._HasGceCreds():
      try:
        return credentials_lib.GceAssertionCredentials(
            cache_filename=GetGceCredentialCacheFilename())
      except apitools_exceptions.ResourceUnavailableError, e:
        if 'service account' in str(e) and 'does not exist' in str(e):
          return None
        raise

  def _GetDevshellCreds(self):
    try:
      return devshell.DevshellCredentials()
    except devshell.NoDevshellServer:
      return None
    except:
      raise

  def _GetCredentialStoreKeyDict(self, credentials):
    """Disambiguates a credential for caching in a credential store.

    Different credential types have different fields that identify them.
    This function assembles relevant information in a dict and returns it.

    Args:
      credentials: An OAuth2Credentials object.

    Returns:
      Dict of relevant identifiers for credentials.
    """
    # TODO: If scopes ever become available in the credentials themselves,
    # include them in the key dict.
    key_dict = {'api_version': self.api_version}
    # pylint: disable=protected-access
    if isinstance(credentials, devshell.DevshellCredentials):
      key_dict['user_email'] = credentials.user_email
    elif isinstance(credentials,
                    oauth2client.service_account._ServiceAccountCredentials):
      key_dict['_service_account_email'] = credentials._service_account_email
    elif isinstance(credentials,
                    oauth2client.client.SignedJwtAssertionCredentials):
      key_dict['service_account_name'] = credentials.service_account_name
    elif isinstance(credentials, oauth2client.client.OAuth2Credentials):
      if credentials.client_id and credentials.client_id != 'null':
        key_dict['client_id'] = credentials.client_id
      key_dict['refresh_token'] = credentials.refresh_token
    # pylint: enable=protected-access

    return key_dict

  def _GetNewDownloadHttp(self):
    return GetNewHttp(http_class=HttpWithDownloadStream)

  def _GetNewUploadHttp(self):
    """Returns an upload-safe Http object (by disabling httplib2 retries)."""
    return GetNewHttp(http_class=HttpWithNoRetries)

  def GetBucket(self, bucket_name, provider=None, fields=None):
    """See CloudApi class for function doc strings."""
    projection = (apitools_messages.StorageBucketsGetRequest
                  .ProjectionValueValuesEnum.full)
    apitools_request = apitools_messages.StorageBucketsGetRequest(
        bucket=bucket_name, projection=projection)
    global_params = apitools_messages.StandardQueryParameters()
    if fields:
      global_params.fields = ','.join(set(fields))

    # Here and in list buckets, we have no way of knowing
    # whether we requested a field and didn't get it because it didn't exist
    # or because we didn't have permission to access it.
    try:
      return self.api_client.buckets.Get(apitools_request,
                                         global_params=global_params)
    except TRANSLATABLE_APITOOLS_EXCEPTIONS, e:
      self._TranslateExceptionAndRaise(e, bucket_name=bucket_name)

  def PatchBucket(self, bucket_name, metadata, canned_acl=None,
                  canned_def_acl=None, preconditions=None, provider=None,
                  fields=None):
    """See CloudApi class for function doc strings."""
    projection = (apitools_messages.StorageBucketsPatchRequest
                  .ProjectionValueValuesEnum.full)
    bucket_metadata = metadata

    if not preconditions:
      preconditions = Preconditions()

    # For blank metadata objects, we need to explicitly call
    # them out to apitools so it will send/erase them.
    apitools_include_fields = []
    for metadata_field in ('metadata', 'lifecycle', 'logging', 'versioning',
                           'website'):
      attr = getattr(bucket_metadata, metadata_field, None)
      if attr and not encoding.MessageToDict(attr):
        setattr(bucket_metadata, metadata_field, None)
        apitools_include_fields.append(metadata_field)

    if bucket_metadata.cors and bucket_metadata.cors == REMOVE_CORS_CONFIG:
      bucket_metadata.cors = []
      apitools_include_fields.append('cors')

    if (bucket_metadata.defaultObjectAcl and
        bucket_metadata.defaultObjectAcl[0] == PRIVATE_DEFAULT_OBJ_ACL):
      bucket_metadata.defaultObjectAcl = []
      apitools_include_fields.append('defaultObjectAcl')

    predefined_acl = None
    if canned_acl:
      # Must null out existing ACLs to apply a canned ACL.
      apitools_include_fields.append('acl')
      predefined_acl = (
          apitools_messages.StorageBucketsPatchRequest.
          PredefinedAclValueValuesEnum(
              self._BucketCannedAclToPredefinedAcl(canned_acl)))

    predefined_def_acl = None
    if canned_def_acl:
      # Must null out existing default object ACLs to apply a canned ACL.
      apitools_include_fields.append('defaultObjectAcl')
      predefined_def_acl = (
          apitools_messages.StorageBucketsPatchRequest.
          PredefinedDefaultObjectAclValueValuesEnum(
              self._ObjectCannedAclToPredefinedAcl(canned_def_acl)))

    apitools_request = apitools_messages.StorageBucketsPatchRequest(
        bucket=bucket_name, bucketResource=bucket_metadata,
        projection=projection,
        ifMetagenerationMatch=preconditions.meta_gen_match,
        predefinedAcl=predefined_acl,
        predefinedDefaultObjectAcl=predefined_def_acl)
    global_params = apitools_messages.StandardQueryParameters()
    if fields:
      global_params.fields = ','.join(set(fields))
    with self.api_client.IncludeFields(apitools_include_fields):
      try:
        return self.api_client.buckets.Patch(apitools_request,
                                             global_params=global_params)
      except TRANSLATABLE_APITOOLS_EXCEPTIONS, e:
        self._TranslateExceptionAndRaise(e)

  def CreateBucket(self, bucket_name, project_id=None, metadata=None,
                   provider=None, fields=None):
    """See CloudApi class for function doc strings."""
    projection = (apitools_messages.StorageBucketsInsertRequest
                  .ProjectionValueValuesEnum.full)
    if not metadata:
      metadata = apitools_messages.Bucket()
    metadata.name = bucket_name

    if metadata.location:
      metadata.location = metadata.location.upper()
    if metadata.storageClass:
      metadata.storageClass = metadata.storageClass.upper()

    project_id = PopulateProjectId(project_id)

    apitools_request = apitools_messages.StorageBucketsInsertRequest(
        bucket=metadata, project=project_id, projection=projection)
    global_params = apitools_messages.StandardQueryParameters()
    if fields:
      global_params.fields = ','.join(set(fields))
    try:
      return self.api_client.buckets.Insert(apitools_request,
                                            global_params=global_params)
    except TRANSLATABLE_APITOOLS_EXCEPTIONS, e:
      self._TranslateExceptionAndRaise(e, bucket_name=bucket_name)

  def DeleteBucket(self, bucket_name, preconditions=None, provider=None):
    """See CloudApi class for function doc strings."""
    if not preconditions:
      preconditions = Preconditions()

    apitools_request = apitools_messages.StorageBucketsDeleteRequest(
        bucket=bucket_name, ifMetagenerationMatch=preconditions.meta_gen_match)

    try:
      self.api_client.buckets.Delete(apitools_request)
    except TRANSLATABLE_APITOOLS_EXCEPTIONS, e:
      if isinstance(
          self._TranslateApitoolsException(e, bucket_name=bucket_name),
          NotEmptyException):
        # If bucket is not empty, check to see if versioning is enabled and
        # signal that in the exception if it is.
        bucket_metadata = self.GetBucket(bucket_name,
                                         fields=['versioning'])
        if bucket_metadata.versioning and bucket_metadata.versioning.enabled:
          raise NotEmptyException('VersionedBucketNotEmpty',
                                  status=e.status_code)
      self._TranslateExceptionAndRaise(e, bucket_name=bucket_name)

  def ListBuckets(self, project_id=None, provider=None, fields=None):
    """See CloudApi class for function doc strings."""
    projection = (apitools_messages.StorageBucketsListRequest
                  .ProjectionValueValuesEnum.full)
    project_id = PopulateProjectId(project_id)

    apitools_request = apitools_messages.StorageBucketsListRequest(
        project=project_id, maxResults=NUM_BUCKETS_PER_LIST_PAGE,
        projection=projection)
    global_params = apitools_messages.StandardQueryParameters()
    if fields:
      if 'nextPageToken' not in fields:
        fields.add('nextPageToken')
      global_params.fields = ','.join(set(fields))
    try:
      bucket_list = self.api_client.buckets.List(apitools_request,
                                                 global_params=global_params)
    except TRANSLATABLE_APITOOLS_EXCEPTIONS, e:
      self._TranslateExceptionAndRaise(e)

    for bucket in self._YieldBuckets(bucket_list):
      yield bucket

    while bucket_list.nextPageToken:
      apitools_request = apitools_messages.StorageBucketsListRequest(
          project=project_id, pageToken=bucket_list.nextPageToken,
          maxResults=NUM_BUCKETS_PER_LIST_PAGE, projection=projection)
      try:
        bucket_list = self.api_client.buckets.List(apitools_request,
                                                   global_params=global_params)
      except TRANSLATABLE_APITOOLS_EXCEPTIONS, e:
        self._TranslateExceptionAndRaise(e)

      for bucket in self._YieldBuckets(bucket_list):
        yield bucket

  def _YieldBuckets(self, bucket_list):
    """Yields buckets from a list returned by apitools."""
    if bucket_list.items:
      for bucket in bucket_list.items:
        yield bucket

  def ListObjects(self, bucket_name, prefix=None, delimiter=None,
                  all_versions=None, provider=None, fields=None):
    """See CloudApi class for function doc strings."""
    projection = (apitools_messages.StorageObjectsListRequest
                  .ProjectionValueValuesEnum.full)
    apitools_request = apitools_messages.StorageObjectsListRequest(
        bucket=bucket_name, prefix=prefix, delimiter=delimiter,
        versions=all_versions, projection=projection,
        maxResults=NUM_OBJECTS_PER_LIST_PAGE)
    global_params = apitools_messages.StandardQueryParameters()

    if fields:
      fields = set(fields)
      if 'nextPageToken' not in fields:
        fields.add('nextPageToken')
      global_params.fields = ','.join(fields)

    try:
      object_list = self.api_client.objects.List(apitools_request,
                                                 global_params=global_params)
    except TRANSLATABLE_APITOOLS_EXCEPTIONS, e:
      self._TranslateExceptionAndRaise(e, bucket_name=bucket_name)

    for object_or_prefix in self._YieldObjectsAndPrefixes(object_list):
      yield object_or_prefix

    while object_list.nextPageToken:
      apitools_request = apitools_messages.StorageObjectsListRequest(
          bucket=bucket_name, prefix=prefix, delimiter=delimiter,
          versions=all_versions, projection=projection,
          pageToken=object_list.nextPageToken,
          maxResults=NUM_OBJECTS_PER_LIST_PAGE)
      try:
        object_list = self.api_client.objects.List(apitools_request,
                                                   global_params=global_params)
      except TRANSLATABLE_APITOOLS_EXCEPTIONS, e:
        self._TranslateExceptionAndRaise(e, bucket_name=bucket_name)

      for object_or_prefix in self._YieldObjectsAndPrefixes(object_list):
        yield object_or_prefix

  def _YieldObjectsAndPrefixes(self, object_list):
    # Yield prefixes first so that checking for the presence of a subdirectory
    # is fast.
    if object_list.prefixes:
      for prefix in object_list.prefixes:
        yield CloudApi.CsObjectOrPrefix(prefix,
                                        CloudApi.CsObjectOrPrefixType.PREFIX)
    if object_list.items:
      for cloud_obj in object_list.items:
        yield CloudApi.CsObjectOrPrefix(cloud_obj,
                                        CloudApi.CsObjectOrPrefixType.OBJECT)

  def GetObjectMetadata(self, bucket_name, object_name, generation=None,
                        provider=None, fields=None):
    """See CloudApi class for function doc strings."""
    projection = (apitools_messages.StorageObjectsGetRequest
                  .ProjectionValueValuesEnum.full)

    if generation:
      generation = long(generation)

    apitools_request = apitools_messages.StorageObjectsGetRequest(
        bucket=bucket_name, object=object_name, projection=projection,
        generation=generation)
    global_params = apitools_messages.StandardQueryParameters()
    if fields:
      global_params.fields = ','.join(set(fields))

    try:
      return self.api_client.objects.Get(apitools_request,
                                         global_params=global_params)
    except TRANSLATABLE_APITOOLS_EXCEPTIONS, e:
      self._TranslateExceptionAndRaise(e, bucket_name=bucket_name,
                                       object_name=object_name,
                                       generation=generation)

  def GetObjectMedia(
      self, bucket_name, object_name, download_stream,
      provider=None, generation=None, object_size=None,
      download_strategy=CloudApi.DownloadStrategy.ONE_SHOT, start_byte=0,
      end_byte=None, progress_callback=None, serialization_data=None,
      digesters=None):
    """See CloudApi class for function doc strings."""
    # This implementation will get the object metadata first if we don't pass it
    # in via serialization_data.
    if generation:
      generation = long(generation)

    # 'outer_total_size' is only used for formatting user output, and is
    # expected to be one higher than the last byte that should be downloaded.
    # TODO: Change DownloadCallbackConnectionClassFactory and progress callbacks
    # to more elegantly handle total size for components of files.
    outer_total_size = object_size
    if end_byte:
      outer_total_size = end_byte + 1
    elif serialization_data:
      outer_total_size = json.loads(serialization_data)['total_size']

    if progress_callback:
      if outer_total_size is None:
        raise ArgumentException('Download size is required when callbacks are '
                                'requested for a download, but no size was '
                                'provided.')
      progress_callback(start_byte, outer_total_size)

    bytes_downloaded_container = BytesTransferredContainer()
    bytes_downloaded_container.bytes_transferred = start_byte

    callback_class_factory = DownloadCallbackConnectionClassFactory(
        bytes_downloaded_container, total_size=outer_total_size,
        progress_callback=progress_callback, digesters=digesters)
    download_http_class = callback_class_factory.GetConnectionClass()

    # Point our download HTTP at our download stream.
    self.download_http.stream = download_stream
    self.download_http.connections = {'https': download_http_class}

    if serialization_data:
      apitools_download = apitools_transfer.Download.FromData(
          download_stream, serialization_data, self.api_client.http,
          num_retries=self.num_retries)
    else:
      apitools_download = apitools_transfer.Download.FromStream(
          download_stream, auto_transfer=False, total_size=object_size,
          num_retries=self.num_retries)

    apitools_download.bytes_http = self.authorized_download_http
    apitools_request = apitools_messages.StorageObjectsGetRequest(
        bucket=bucket_name, object=object_name, generation=generation)

    try:
      if download_strategy == CloudApi.DownloadStrategy.RESUMABLE:
        # Disable retries in apitools. We will handle them explicitly here.
        apitools_download.retry_func = (
            apitools_http_wrapper.RethrowExceptionHandler)
        return self._PerformResumableDownload(
            bucket_name, object_name, download_stream, apitools_request,
            apitools_download, bytes_downloaded_container,
            generation=generation, start_byte=start_byte, end_byte=end_byte,
            serialization_data=serialization_data)
      else:
        return self._PerformDownload(
            bucket_name, object_name, download_stream, apitools_request,
            apitools_download, generation=generation, start_byte=start_byte,
            end_byte=end_byte, serialization_data=serialization_data)
    except TRANSLATABLE_APITOOLS_EXCEPTIONS, e:
      self._TranslateExceptionAndRaise(e, bucket_name=bucket_name,
                                       object_name=object_name,
                                       generation=generation)

  def _PerformResumableDownload(
      self, bucket_name, object_name, download_stream, apitools_request,
      apitools_download, bytes_downloaded_container, generation=None,
      start_byte=0, end_byte=None, serialization_data=None):
    retries = 0
    last_progress_byte = start_byte
    while retries <= self.num_retries:
      try:
        return self._PerformDownload(
            bucket_name, object_name, download_stream, apitools_request,
            apitools_download, generation=generation, start_byte=start_byte,
            end_byte=end_byte, serialization_data=serialization_data)
      except HTTP_TRANSFER_EXCEPTIONS, e:
        start_byte = download_stream.tell()
        bytes_downloaded_container.bytes_transferred = start_byte
        if start_byte > last_progress_byte:
          # We've made progress, so allow a fresh set of retries.
          last_progress_byte = start_byte
          retries = 0
        retries += 1
        if retries > self.num_retries:
          raise ResumableDownloadException(
              'Transfer failed after %d retries. Final exception: %s' %
              (self.num_retries, unicode(e).encode(UTF8)))
        time.sleep(CalculateWaitForRetry(retries, max_wait=self.max_retry_wait))
        if self.logger.isEnabledFor(logging.DEBUG):
          self.logger.debug(
              'Retrying download from byte %s after exception: %s. Trace: %s',
              start_byte, unicode(e).encode(UTF8), traceback.format_exc())
        apitools_http_wrapper.RebuildHttpConnections(
            apitools_download.bytes_http)

  def _PerformDownload(
      self, bucket_name, object_name, download_stream, apitools_request,
      apitools_download, generation=None, start_byte=0, end_byte=None,
      serialization_data=None):
    if not serialization_data:
      try:
        self.api_client.objects.Get(apitools_request,
                                    download=apitools_download)
      except TRANSLATABLE_APITOOLS_EXCEPTIONS, e:
        self._TranslateExceptionAndRaise(e, bucket_name=bucket_name,
                                         object_name=object_name,
                                         generation=generation)

    # Disable apitools' default print callbacks.
    def _NoOpCallback(unused_response, unused_download_object):
      pass

    # TODO: If we have a resumable download with accept-encoding:gzip
    # on a object that is compressible but not in gzip form in the cloud,
    # on-the-fly compression will gzip the object.  In this case if our
    # download breaks, future requests will ignore the range header and just
    # return the object (gzipped) in its entirety.  Ideally, we would unzip
    # the bytes that we have locally and send a range request without
    # accept-encoding:gzip so that we can download only the (uncompressed) bytes
    # that we don't yet have.

    # Since bytes_http is created in this function, we don't get the
    # user-agent header from api_client's http automatically.
    additional_headers = {
        'accept-encoding': 'gzip',
        'user-agent': self.api_client.user_agent
    }
    if start_byte or end_byte is not None:
      apitools_download.GetRange(additional_headers=additional_headers,
                                 start=start_byte, end=end_byte,
                                 use_chunks=False)
    else:
      apitools_download.StreamMedia(
          callback=_NoOpCallback, finish_callback=_NoOpCallback,
          additional_headers=additional_headers, use_chunks=False)
    return apitools_download.encoding

  def PatchObjectMetadata(self, bucket_name, object_name, metadata,
                          canned_acl=None, generation=None, preconditions=None,
                          provider=None, fields=None):
    """See CloudApi class for function doc strings."""
    projection = (apitools_messages.StorageObjectsPatchRequest
                  .ProjectionValueValuesEnum.full)

    if not preconditions:
      preconditions = Preconditions()

    if generation:
      generation = long(generation)

    predefined_acl = None
    apitools_include_fields = []
    if canned_acl:
      # Must null out existing ACLs to apply a canned ACL.
      apitools_include_fields.append('acl')
      predefined_acl = (
          apitools_messages.StorageObjectsPatchRequest.
          PredefinedAclValueValuesEnum(
              self._ObjectCannedAclToPredefinedAcl(canned_acl)))

    apitools_request = apitools_messages.StorageObjectsPatchRequest(
        bucket=bucket_name, object=object_name, objectResource=metadata,
        generation=generation, projection=projection,
        ifGenerationMatch=preconditions.gen_match,
        ifMetagenerationMatch=preconditions.meta_gen_match,
        predefinedAcl=predefined_acl)
    global_params = apitools_messages.StandardQueryParameters()
    if fields:
      global_params.fields = ','.join(set(fields))

    try:
      with self.api_client.IncludeFields(apitools_include_fields):
        return self.api_client.objects.Patch(apitools_request,
                                             global_params=global_params)
    except TRANSLATABLE_APITOOLS_EXCEPTIONS, e:
      self._TranslateExceptionAndRaise(e, bucket_name=bucket_name,
                                       object_name=object_name,
                                       generation=generation)

  def _UploadObject(self, upload_stream, object_metadata, canned_acl=None,
                    size=None, preconditions=None, provider=None, fields=None,
                    serialization_data=None, tracker_callback=None,
                    progress_callback=None,
                    apitools_strategy=apitools_transfer.SIMPLE_UPLOAD,
                    total_size=0):
    # pylint: disable=g-doc-args
    """Upload implementation. Cloud API arguments, plus two more.

    Additional args:
      apitools_strategy: SIMPLE_UPLOAD or RESUMABLE_UPLOAD.
      total_size: Total size of the upload; None if it is unknown (streaming).

    Returns:
      Uploaded object metadata.
    """
    # pylint: enable=g-doc-args
    ValidateDstObjectMetadata(object_metadata)
    predefined_acl = None
    if canned_acl:
      predefined_acl = (
          apitools_messages.StorageObjectsInsertRequest.
          PredefinedAclValueValuesEnum(
              self._ObjectCannedAclToPredefinedAcl(canned_acl)))

    bytes_uploaded_container = BytesTransferredContainer()

    if progress_callback and size:
      total_size = size
      progress_callback(0, size)

    callback_class_factory = UploadCallbackConnectionClassFactory(
        bytes_uploaded_container, total_size=total_size,
        progress_callback=progress_callback)

    upload_http_class = callback_class_factory.GetConnectionClass()
    self.upload_http.connections = {'http': upload_http_class,
                                    'https': upload_http_class}

    # Since bytes_http is created in this function, we don't get the
    # user-agent header from api_client's http automatically.
    additional_headers = {
        'user-agent': self.api_client.user_agent
    }

    try:
      content_type = None
      apitools_request = None
      global_params = None
      if not serialization_data:
        # This is a new upload, set up initial upload state.
        content_type = object_metadata.contentType
        if not content_type:
          content_type = DEFAULT_CONTENT_TYPE

        if not preconditions:
          preconditions = Preconditions()

        apitools_request = apitools_messages.StorageObjectsInsertRequest(
            bucket=object_metadata.bucket, object=object_metadata,
            ifGenerationMatch=preconditions.gen_match,
            ifMetagenerationMatch=preconditions.meta_gen_match,
            predefinedAcl=predefined_acl)
        global_params = apitools_messages.StandardQueryParameters()
        if fields:
          global_params.fields = ','.join(set(fields))

      if apitools_strategy == apitools_transfer.SIMPLE_UPLOAD:
        # One-shot upload.
        apitools_upload = apitools_transfer.Upload(
            upload_stream, content_type, total_size=size, auto_transfer=True,
            num_retries=self.num_retries)
        apitools_upload.strategy = apitools_strategy
        apitools_upload.bytes_http = self.authorized_upload_http

        return self.api_client.objects.Insert(
            apitools_request,
            upload=apitools_upload,
            global_params=global_params)
      else:  # Resumable upload.
        return self._PerformResumableUpload(
            upload_stream, self.authorized_upload_http, content_type, size,
            serialization_data, apitools_strategy, apitools_request,
            global_params, bytes_uploaded_container, tracker_callback,
            additional_headers, progress_callback)
    except TRANSLATABLE_APITOOLS_EXCEPTIONS, e:
      not_found_exception = CreateNotFoundExceptionForObjectWrite(
          self.provider, object_metadata.bucket)
      self._TranslateExceptionAndRaise(e, bucket_name=object_metadata.bucket,
                                       object_name=object_metadata.name,
                                       not_found_exception=not_found_exception)

  def _PerformResumableUpload(
      self, upload_stream, authorized_upload_http, content_type, size,
      serialization_data, apitools_strategy, apitools_request, global_params,
      bytes_uploaded_container, tracker_callback, addl_headers,
      progress_callback):
    try:
      if serialization_data:
        # Resuming an existing upload.
        apitools_upload = apitools_transfer.Upload.FromData(
            upload_stream, serialization_data, self.api_client.http,
            num_retries=self.num_retries)
        apitools_upload.chunksize = GetJsonResumableChunkSize()
        apitools_upload.bytes_http = authorized_upload_http
      else:
        # New resumable upload.
        apitools_upload = apitools_transfer.Upload(
            upload_stream, content_type, total_size=size,
            chunksize=GetJsonResumableChunkSize(), auto_transfer=False,
            num_retries=self.num_retries)
        apitools_upload.strategy = apitools_strategy
        apitools_upload.bytes_http = authorized_upload_http
        self.api_client.objects.Insert(
            apitools_request,
            upload=apitools_upload,
            global_params=global_params)
      # Disable retries in apitools. We will handle them explicitly here.
      apitools_upload.retry_func = (
          apitools_http_wrapper.RethrowExceptionHandler)

      # Disable apitools' default print callbacks.
      def _NoOpCallback(unused_response, unused_upload_object):
        pass

      # If we're resuming an upload, apitools has at this point received
      # from the server how many bytes it already has. Update our
      # callback class with this information.
      bytes_uploaded_container.bytes_transferred = apitools_upload.progress
      if tracker_callback:
        tracker_callback(json.dumps(apitools_upload.serialization_data))

      retries = 0
      last_progress_byte = apitools_upload.progress
      while retries <= self.num_retries:
        try:
          # TODO: On retry, this will seek to the bytes that the server has,
          # causing the hash to be recalculated. Make HashingFileUploadWrapper
          # save a digest according to json_resumable_chunk_size.
          if size:
            # If size is known, we can send it all in one request and avoid
            # making a round-trip per chunk.
            http_response = apitools_upload.StreamMedia(
                callback=_NoOpCallback, finish_callback=_NoOpCallback,
                additional_headers=addl_headers)
          else:
            # Otherwise it's a streaming request and we need to ensure that we
            # send the bytes in chunks so that we can guarantee that we never
            # need to seek backwards more than our buffer (and also that the
            # chunks are aligned to 256KB).
            http_response = apitools_upload.StreamInChunks(
                callback=_NoOpCallback, finish_callback=_NoOpCallback,
                additional_headers=addl_headers)
          processed_response = self.api_client.objects.ProcessHttpResponse(
              self.api_client.objects.GetMethodConfig('Insert'), http_response)
          if size is None and progress_callback:
            # Make final progress callback; total size should now be known.
            # This works around the fact the send function counts header bytes.
            # However, this will make the progress appear to go slightly
            # backwards at the end.
            progress_callback(apitools_upload.total_size,
                              apitools_upload.total_size)
          return processed_response
        except HTTP_TRANSFER_EXCEPTIONS, e:
          apitools_http_wrapper.RebuildHttpConnections(
              apitools_upload.bytes_http)
          while retries <= self.num_retries:
            try:
              # TODO: Simulate the refresh case in tests. Right now, our
              # mocks are not complex enough to simulate a failure.
              apitools_upload.RefreshResumableUploadState()
              start_byte = apitools_upload.progress
              bytes_uploaded_container.bytes_transferred = start_byte
              break
            except HTTP_TRANSFER_EXCEPTIONS, e2:
              apitools_http_wrapper.RebuildHttpConnections(
                  apitools_upload.bytes_http)
              retries += 1
              if retries > self.num_retries:
                raise ResumableUploadException(
                    'Transfer failed after %d retries. Final exception: %s' %
                    (self.num_retries, e2))
              time.sleep(
                  CalculateWaitForRetry(retries, max_wait=self.max_retry_wait))
          if start_byte > last_progress_byte:
            # We've made progress, so allow a fresh set of retries.
            last_progress_byte = start_byte
            retries = 0
          else:
            retries += 1
            if retries > self.num_retries:
              raise ResumableUploadException(
                  'Transfer failed after %d retries. Final exception: %s' %
                  (self.num_retries, unicode(e).encode(UTF8)))
            time.sleep(
                CalculateWaitForRetry(retries, max_wait=self.max_retry_wait))
          if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(
                'Retrying upload from byte %s after exception: %s. Trace: %s',
                start_byte, unicode(e).encode(UTF8), traceback.format_exc())
    except TRANSLATABLE_APITOOLS_EXCEPTIONS, e:
      resumable_ex = self._TranslateApitoolsResumableUploadException(e)
      if resumable_ex:
        raise resumable_ex
      else:
        raise

  def UploadObject(self, upload_stream, object_metadata, canned_acl=None,
                   size=None, preconditions=None, progress_callback=None,
                   provider=None, fields=None):
    """See CloudApi class for function doc strings."""
    return self._UploadObject(
        upload_stream, object_metadata, canned_acl=canned_acl,
        size=size, preconditions=preconditions,
        progress_callback=progress_callback, fields=fields,
        apitools_strategy=apitools_transfer.SIMPLE_UPLOAD)

  def UploadObjectStreaming(self, upload_stream, object_metadata,
                            canned_acl=None, preconditions=None,
                            progress_callback=None, provider=None,
                            fields=None):
    """See CloudApi class for function doc strings."""
    # Streaming indicated by not passing a size.
    # Resumable capabilities are present up to the resumable chunk size using
    # a buffered stream.
    return self._UploadObject(
        upload_stream, object_metadata, canned_acl=canned_acl,
        preconditions=preconditions, progress_callback=progress_callback,
        fields=fields, apitools_strategy=apitools_transfer.RESUMABLE_UPLOAD,
        total_size=None)

  def UploadObjectResumable(
      self, upload_stream, object_metadata, canned_acl=None, preconditions=None,
      provider=None, fields=None, size=None, serialization_data=None,
      tracker_callback=None, progress_callback=None):
    """See CloudApi class for function doc strings."""
    return self._UploadObject(
        upload_stream, object_metadata, canned_acl=canned_acl,
        preconditions=preconditions, fields=fields, size=size,
        serialization_data=serialization_data,
        tracker_callback=tracker_callback, progress_callback=progress_callback,
        apitools_strategy=apitools_transfer.RESUMABLE_UPLOAD)

  def CopyObject(self, src_obj_metadata, dst_obj_metadata, src_generation=None,
                 canned_acl=None, preconditions=None, progress_callback=None,
                 max_bytes_per_call=None, provider=None, fields=None):
    """See CloudApi class for function doc strings."""
    ValidateDstObjectMetadata(dst_obj_metadata)
    predefined_acl = None
    if canned_acl:
      predefined_acl = (
          apitools_messages.StorageObjectsRewriteRequest.
          DestinationPredefinedAclValueValuesEnum(
              self._ObjectCannedAclToPredefinedAcl(canned_acl)))

    if src_generation:
      src_generation = long(src_generation)

    if not preconditions:
      preconditions = Preconditions()

    projection = (apitools_messages.StorageObjectsRewriteRequest.
                  ProjectionValueValuesEnum.full)
    global_params = apitools_messages.StandardQueryParameters()
    if fields:
      # Rewrite returns the resultant object under the 'resource' field.
      new_fields = set(['done', 'objectSize', 'rewriteToken',
                        'totalBytesRewritten'])
      for field in fields:
        new_fields.add('resource/' + field)
      global_params.fields = ','.join(set(new_fields))

    # Check to see if we are resuming a rewrite.
    tracker_file_name = GetRewriteTrackerFilePath(
        src_obj_metadata.bucket, src_obj_metadata.name, dst_obj_metadata.bucket,
        dst_obj_metadata.name, 'JSON')
    rewrite_params_hash = HashRewriteParameters(
        src_obj_metadata, dst_obj_metadata, projection,
        src_generation=src_generation, gen_match=preconditions.gen_match,
        meta_gen_match=preconditions.meta_gen_match,
        canned_acl=predefined_acl, fields=global_params.fields,
        max_bytes_per_call=max_bytes_per_call)
    resume_rewrite_token = ReadRewriteTrackerFile(tracker_file_name,
                                                  rewrite_params_hash)

    progress_cb_with_backoff = None
    try:
      last_bytes_written = 0L
      while True:
        apitools_request = apitools_messages.StorageObjectsRewriteRequest(
            sourceBucket=src_obj_metadata.bucket,
            sourceObject=src_obj_metadata.name,
            destinationBucket=dst_obj_metadata.bucket,
            destinationObject=dst_obj_metadata.name,
            projection=projection, object=dst_obj_metadata,
            sourceGeneration=src_generation,
            ifGenerationMatch=preconditions.gen_match,
            ifMetagenerationMatch=preconditions.meta_gen_match,
            destinationPredefinedAcl=predefined_acl,
            rewriteToken=resume_rewrite_token,
            maxBytesRewrittenPerCall=max_bytes_per_call)
        rewrite_response = self.api_client.objects.Rewrite(
            apitools_request, global_params=global_params)
        bytes_written = long(rewrite_response.totalBytesRewritten)
        if progress_callback and not progress_cb_with_backoff:
          progress_cb_with_backoff = ProgressCallbackWithBackoff(
              long(rewrite_response.objectSize), progress_callback)
        if progress_cb_with_backoff:
          progress_cb_with_backoff.Progress(
              bytes_written - last_bytes_written)

        if rewrite_response.done:
          break
        elif not resume_rewrite_token:
          # Save the token and make a tracker file if they don't already exist.
          resume_rewrite_token = rewrite_response.rewriteToken
          WriteRewriteTrackerFile(tracker_file_name, rewrite_params_hash,
                                  rewrite_response.rewriteToken)
        last_bytes_written = bytes_written

      DeleteTrackerFile(tracker_file_name)
      return rewrite_response.resource
    except TRANSLATABLE_APITOOLS_EXCEPTIONS, e:
      not_found_exception = CreateNotFoundExceptionForObjectWrite(
          self.provider, dst_obj_metadata.bucket, src_provider=self.provider,
          src_bucket_name=src_obj_metadata.bucket,
          src_object_name=src_obj_metadata.name, src_generation=src_generation)
      self._TranslateExceptionAndRaise(e, bucket_name=dst_obj_metadata.bucket,
                                       object_name=dst_obj_metadata.name,
                                       not_found_exception=not_found_exception)

  def DeleteObject(self, bucket_name, object_name, preconditions=None,
                   generation=None, provider=None):
    """See CloudApi class for function doc strings."""
    if not preconditions:
      preconditions = Preconditions()

    if generation:
      generation = long(generation)

    apitools_request = apitools_messages.StorageObjectsDeleteRequest(
        bucket=bucket_name, object=object_name, generation=generation,
        ifGenerationMatch=preconditions.gen_match,
        ifMetagenerationMatch=preconditions.meta_gen_match)
    try:
      return self.api_client.objects.Delete(apitools_request)
    except TRANSLATABLE_APITOOLS_EXCEPTIONS, e:
      self._TranslateExceptionAndRaise(e, bucket_name=bucket_name,
                                       object_name=object_name,
                                       generation=generation)

  def ComposeObject(self, src_objs_metadata, dst_obj_metadata,
                    preconditions=None, provider=None, fields=None):
    """See CloudApi class for function doc strings."""
    ValidateDstObjectMetadata(dst_obj_metadata)

    dst_obj_name = dst_obj_metadata.name
    dst_obj_metadata.name = None
    dst_bucket_name = dst_obj_metadata.bucket
    dst_obj_metadata.bucket = None
    if not dst_obj_metadata.contentType:
      dst_obj_metadata.contentType = DEFAULT_CONTENT_TYPE

    if not preconditions:
      preconditions = Preconditions()

    global_params = apitools_messages.StandardQueryParameters()
    if fields:
      global_params.fields = ','.join(set(fields))

    src_objs_compose_request = apitools_messages.ComposeRequest(
        sourceObjects=src_objs_metadata, destination=dst_obj_metadata)

    apitools_request = apitools_messages.StorageObjectsComposeRequest(
        composeRequest=src_objs_compose_request,
        destinationBucket=dst_bucket_name,
        destinationObject=dst_obj_name,
        ifGenerationMatch=preconditions.gen_match,
        ifMetagenerationMatch=preconditions.meta_gen_match)
    try:
      return self.api_client.objects.Compose(apitools_request,
                                             global_params=global_params)
    except TRANSLATABLE_APITOOLS_EXCEPTIONS, e:
      # We can't be sure which object was missing in the 404 case.
      if isinstance(e, apitools_exceptions.HttpError) and e.status_code == 404:
        raise NotFoundException('One of the source objects does not exist.')
      else:
        self._TranslateExceptionAndRaise(e)

  def WatchBucket(self, bucket_name, address, channel_id, token=None,
                  provider=None, fields=None):
    """See CloudApi class for function doc strings."""
    projection = (apitools_messages.StorageObjectsWatchAllRequest
                  .ProjectionValueValuesEnum.full)

    channel = apitools_messages.Channel(address=address, id=channel_id,
                                        token=token, type='WEB_HOOK')

    apitools_request = apitools_messages.StorageObjectsWatchAllRequest(
        bucket=bucket_name, channel=channel, projection=projection)

    global_params = apitools_messages.StandardQueryParameters()
    if fields:
      global_params.fields = ','.join(set(fields))

    try:
      return self.api_client.objects.WatchAll(apitools_request,
                                              global_params=global_params)
    except TRANSLATABLE_APITOOLS_EXCEPTIONS, e:
      self._TranslateExceptionAndRaise(e, bucket_name=bucket_name)

  def StopChannel(self, channel_id, resource_id, provider=None):
    """See CloudApi class for function doc strings."""
    channel = apitools_messages.Channel(id=channel_id, resourceId=resource_id)
    try:
      self.api_client.channels.Stop(channel)
    except TRANSLATABLE_APITOOLS_EXCEPTIONS, e:
      self._TranslateExceptionAndRaise(e)

  def _BucketCannedAclToPredefinedAcl(self, canned_acl_string):
    """Translates the input string to a bucket PredefinedAcl string.

    Args:
      canned_acl_string: Canned ACL string.

    Returns:
      String that can be used as a query parameter with the JSON API. This
      corresponds to a flavor of *PredefinedAclValueValuesEnum and can be
      used as input to apitools requests that affect bucket access controls.
    """
    # XML : JSON
    translation_dict = {
        None: None,
        'authenticated-read': 'authenticatedRead',
        'private': 'private',
        'project-private': 'projectPrivate',
        'public-read': 'publicRead',
        'public-read-write': 'publicReadWrite'
    }
    if canned_acl_string in translation_dict:
      return translation_dict[canned_acl_string]
    raise ArgumentException('Invalid canned ACL %s' % canned_acl_string)

  def _ObjectCannedAclToPredefinedAcl(self, canned_acl_string):
    """Translates the input string to an object PredefinedAcl string.

    Args:
      canned_acl_string: Canned ACL string.

    Returns:
      String that can be used as a query parameter with the JSON API. This
      corresponds to a flavor of *PredefinedAclValueValuesEnum and can be
      used as input to apitools requests that affect object access controls.
    """
    # XML : JSON
    translation_dict = {
        None: None,
        'authenticated-read': 'authenticatedRead',
        'bucket-owner-read': 'bucketOwnerRead',
        'bucket-owner-full-control': 'bucketOwnerFullControl',
        'private': 'private',
        'project-private': 'projectPrivate',
        'public-read': 'publicRead'
    }
    if canned_acl_string in translation_dict:
      return translation_dict[canned_acl_string]
    raise ArgumentException('Invalid canned ACL %s' % canned_acl_string)

  def _TranslateExceptionAndRaise(self, e, bucket_name=None, object_name=None,
                                  generation=None, not_found_exception=None):
    """Translates an HTTP exception and raises the translated or original value.

    Args:
      e: Any Exception.
      bucket_name: Optional bucket name in request that caused the exception.
      object_name: Optional object name in request that caused the exception.
      generation: Optional generation in request that caused the exception.
      not_found_exception: Optional exception to raise in the not-found case.

    Raises:
      Translated CloudApi exception, or the original exception if it was not
      translatable.
    """
    translated_exception = self._TranslateApitoolsException(
        e, bucket_name=bucket_name, object_name=object_name,
        generation=generation, not_found_exception=not_found_exception)
    if translated_exception:
      raise translated_exception
    else:
      raise

  def _GetMessageFromHttpError(self, http_error):
    if isinstance(http_error, apitools_exceptions.HttpError):
      if getattr(http_error, 'content', None):
        try:
          json_obj = json.loads(http_error.content)
          if 'error' in json_obj and 'message' in json_obj['error']:
            return json_obj['error']['message']
        except Exception:  # pylint: disable=broad-except
          # If we couldn't decode anything, just leave the message as None.
          pass

  def _TranslateApitoolsResumableUploadException(self, e):
    if isinstance(e, apitools_exceptions.HttpError):
      message = self._GetMessageFromHttpError(e)
      if (e.status_code == 503 and
          self.http.disable_ssl_certificate_validation):
        return ServiceException(_VALIDATE_CERTIFICATES_503_MESSAGE,
                                status=e.status_code)
      elif e.status_code >= 500:
        return ResumableUploadException(
            message or 'Server Error', status=e.status_code)
      elif e.status_code == 429:
        return ResumableUploadException(
            message or 'Too Many Requests', status=e.status_code)
      elif e.status_code == 410:
        return ResumableUploadStartOverException(
            message or 'Bad Request', status=e.status_code)
      elif e.status_code == 404:
        return ResumableUploadStartOverException(
            message or 'Bad Request', status=e.status_code)
      elif e.status_code >= 400:
        return ResumableUploadAbortException(
            message or 'Bad Request', status=e.status_code)
    if isinstance(e, apitools_exceptions.StreamExhausted):
      return ResumableUploadAbortException(e.message)
    if (isinstance(e, apitools_exceptions.TransferError) and
        ('Aborting transfer' in e.message or
         'Not enough bytes in stream' in e.message or
         'additional bytes left in stream' in e.message)):
      return ResumableUploadAbortException(e.message)

  def _TranslateApitoolsException(self, e, bucket_name=None, object_name=None,
                                  generation=None, not_found_exception=None):
    """Translates apitools exceptions into their gsutil Cloud Api equivalents.

    Args:
      e: Any exception in TRANSLATABLE_APITOOLS_EXCEPTIONS.
      bucket_name: Optional bucket name in request that caused the exception.
      object_name: Optional object name in request that caused the exception.
      generation: Optional generation in request that caused the exception.
      not_found_exception: Optional exception to raise in the not-found case.

    Returns:
      CloudStorageApiServiceException for translatable exceptions, None
      otherwise.
    """
    if isinstance(e, apitools_exceptions.HttpError):
      message = self._GetMessageFromHttpError(e)
      if e.status_code == 400:
        # It is possible that the Project ID is incorrect.  Unfortunately the
        # JSON API does not give us much information about what part of the
        # request was bad.
        return BadRequestException(message or 'Bad Request',
                                   status=e.status_code)
      elif e.status_code == 401:
        if 'Login Required' in str(e):
          return AccessDeniedException(
              message or 'Access denied: login required.',
              status=e.status_code)
      elif e.status_code == 403:
        if 'The account for the specified project has been disabled' in str(e):
          return AccessDeniedException(message or 'Account disabled.',
                                       status=e.status_code)
        elif 'Daily Limit for Unauthenticated Use Exceeded' in str(e):
          return AccessDeniedException(
              message or 'Access denied: quota exceeded. '
              'Is your project ID valid?',
              status=e.status_code)
        elif 'The bucket you tried to delete was not empty.' in str(e):
          return NotEmptyException('BucketNotEmpty (%s)' % bucket_name,
                                   status=e.status_code)
        elif ('The bucket you tried to create requires domain ownership '
              'verification.' in str(e)):
          return AccessDeniedException(
              'The bucket you tried to create requires domain ownership '
              'verification. Please see '
              'https://developers.google.com/storage/docs/bucketnaming'
              '?hl=en#verification for more details.', status=e.status_code)
        elif 'User Rate Limit Exceeded' in str(e):
          return AccessDeniedException('Rate limit exceeded. Please retry this '
                                       'request later.', status=e.status_code)
        elif 'Access Not Configured' in str(e):
          return AccessDeniedException(
              'Access Not Configured. Please go to the Google Developers '
              'Console (https://cloud.google.com/console#/project) for your '
              'project, select APIs and Auth and enable the '
              'Google Cloud Storage JSON API.',
              status=e.status_code)
        else:
          return AccessDeniedException(message or e.message,
                                       status=e.status_code)
      elif e.status_code == 404:
        if not_found_exception:
          # The exception is pre-constructed prior to translation; the HTTP
          # status code isn't available at that time.
          setattr(not_found_exception, 'status', e.status_code)
          return not_found_exception
        elif bucket_name:
          if object_name:
            return CreateObjectNotFoundException(e.status_code, self.provider,
                                                 bucket_name, object_name,
                                                 generation=generation)
          return CreateBucketNotFoundException(e.status_code, self.provider,
                                               bucket_name)
        return NotFoundException(e.message, status=e.status_code)

      elif e.status_code == 409 and bucket_name:
        if 'The bucket you tried to delete was not empty.' in str(e):
          return NotEmptyException('BucketNotEmpty (%s)' % bucket_name,
                                   status=e.status_code)
        return ServiceException(
            'Bucket %s already exists.' % bucket_name, status=e.status_code)
      elif e.status_code == 412:
        return PreconditionException(message, status=e.status_code)
      elif (e.status_code == 503 and
            not self.http.disable_ssl_certificate_validation):
        return ServiceException(_VALIDATE_CERTIFICATES_503_MESSAGE,
                                status=e.status_code)
      return ServiceException(message, status=e.status_code)
    elif isinstance(e, apitools_exceptions.TransferInvalidError):
      return ServiceException('Transfer invalid (possible encoding error: %s)'
                              % str(e))
