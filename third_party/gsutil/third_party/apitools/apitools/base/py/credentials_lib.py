#!/usr/bin/env python
"""Common credentials classes and constructors."""
from __future__ import print_function

import datetime
import json
import os

import httplib2
import oauth2client
import oauth2client.client
import oauth2client.gce
import oauth2client.locked_file
import oauth2client.multistore_file
import oauth2client.service_account
from oauth2client import tools  # for gflags declarations
from six.moves import http_client
from six.moves import urllib

from apitools.base.py import exceptions
from apitools.base.py import util

try:
    import gflags
    FLAGS = gflags.FLAGS
except ImportError:
    FLAGS = None


__all__ = [
    'CredentialsFromFile',
    'GaeAssertionCredentials',
    'GceAssertionCredentials',
    'GetCredentials',
    'GetUserinfo',
    'ServiceAccountCredentials',
    'ServiceAccountCredentialsFromFile',
]


# TODO(craigcitro): Expose the extra args here somewhere higher up,
# possibly as flags in the generated CLI.
def GetCredentials(package_name, scopes, client_id, client_secret, user_agent,
                   credentials_filename=None,
                   service_account_name=None, service_account_keyfile=None,
                   service_account_json_keyfile=None,
                   api_key=None,  # pylint: disable=unused-argument
                   client=None):  # pylint: disable=unused-argument
    """Attempt to get credentials, using an oauth dance as the last resort."""
    scopes = util.NormalizeScopes(scopes)
    if ((service_account_name and not service_account_keyfile) or
            (service_account_keyfile and not service_account_name)):
        raise exceptions.CredentialsError(
            'Service account name or keyfile provided without the other')
    # TODO(craigcitro): Error checking.
    client_info = {
        'client_id': client_id,
        'client_secret': client_secret,
        'scope': ' '.join(sorted(util.NormalizeScopes(scopes))),
        'user_agent': user_agent or '%s-generated/0.1' % package_name,
    }
    service_account_kwargs = {
        'user_agent': client_info['user_agent'],
    }
    if service_account_json_keyfile:
        with open(service_account_json_keyfile) as keyfile:
            service_account_info = json.load(keyfile)
        account_type = service_account_info.get('type')
        if account_type != oauth2client.client.SERVICE_ACCOUNT:
            raise exceptions.CredentialsError(
                'Invalid service account credentials: %s' % (
                    service_account_json_keyfile,))
        # pylint: disable=protected-access
        credentials = oauth2client.service_account._ServiceAccountCredentials(
            service_account_id=service_account_info['client_id'],
            service_account_email=service_account_info['client_email'],
            private_key_id=service_account_info['private_key_id'],
            private_key_pkcs8_text=service_account_info['private_key'],
            scopes=scopes,
            **service_account_kwargs)
        # pylint: enable=protected-access
        return credentials
    if service_account_name is not None:
        credentials = ServiceAccountCredentialsFromFile(
            service_account_name, service_account_keyfile, scopes,
            service_account_kwargs=service_account_kwargs)
        if credentials is not None:
            return credentials
    credentials = GaeAssertionCredentials.Get(scopes)
    if credentials is not None:
        return credentials
    credentials = GceAssertionCredentials.Get(scopes)
    if credentials is not None:
        return credentials
    credentials_filename = credentials_filename or os.path.expanduser(
        '~/.apitools.token')
    credentials = CredentialsFromFile(credentials_filename, client_info)
    if credentials is not None:
        return credentials
    raise exceptions.CredentialsError('Could not create valid credentials')


def ServiceAccountCredentialsFromFile(
        service_account_name, private_key_filename, scopes,
        service_account_kwargs=None):
    with open(private_key_filename) as key_file:
        return ServiceAccountCredentials(
            service_account_name, key_file.read(), scopes,
            service_account_kwargs=service_account_kwargs)


def ServiceAccountCredentials(service_account_name, private_key, scopes,
                              service_account_kwargs=None):
    service_account_kwargs = service_account_kwargs or {}
    scopes = util.NormalizeScopes(scopes)
    return oauth2client.client.SignedJwtAssertionCredentials(
        service_account_name, private_key, scopes, **service_account_kwargs)


def _EnsureFileExists(filename):
    """Touches a file; returns False on error, True on success."""
    if not os.path.exists(filename):
        old_umask = os.umask(0o177)
        try:
            open(filename, 'a+b').close()
        except OSError:
            return False
        finally:
            os.umask(old_umask)
    return True


def _OpenNoProxy(request):
    """Wrapper around urllib2.open that ignores proxies."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return opener.open(request)


# TODO(craigcitro): We override to add some utility code, and to
# update the old refresh implementation. Push this code into
# oauth2client.
class GceAssertionCredentials(oauth2client.gce.AppAssertionCredentials):

    """Assertion credentials for GCE instances."""

    def __init__(self, scopes=None, service_account_name='default', **kwds):
        """Initializes the credentials instance.

        Args:
          scopes: The scopes to get. If None, whatever scopes that are
              available to the instance are used.
          service_account_name: The service account to retrieve the scopes
              from.
          **kwds: Additional keyword args.

        """
        # If there is a connectivity issue with the metadata server,
        # detection calls may fail even if we've already successfully
        # identified these scopes in the same execution. However, the
        # available scopes don't change once an instance is created,
        # so there is no reason to perform more than one query.
        #
        # TODO(craigcitro): Move this into oauth2client.
        self.__service_account_name = service_account_name
        cache_filename = None
        cached_scopes = None
        if 'cache_filename' in kwds:
            cache_filename = kwds['cache_filename']
            cached_scopes = self._CheckCacheFileForMatch(
                cache_filename, scopes)

        scopes = cached_scopes or self._ScopesFromMetadataServer(scopes)

        if cache_filename and not cached_scopes:
            self._WriteCacheFile(cache_filename, scopes)

        super(GceAssertionCredentials, self).__init__(scopes, **kwds)

    @classmethod
    def Get(cls, *args, **kwds):
        try:
            return cls(*args, **kwds)
        except exceptions.Error:
            return None

    def _CheckCacheFileForMatch(self, cache_filename, scopes):
        """Checks the cache file to see if it matches the given credentials.

        Args:
          cache_filename: Cache filename to check.
          scopes: Scopes for the desired credentials.

        Returns:
          List of scopes (if cache matches) or None.
        """
        creds = {  # Credentials metadata dict.
            'scopes': sorted(list(scopes)) if scopes else None,
            'svc_acct_name': self.__service_account_name,
        }
        if _EnsureFileExists(cache_filename):
            locked_file = oauth2client.locked_file.LockedFile(
                cache_filename, 'r+b', 'rb')
            try:
                locked_file.open_and_lock()
                cached_creds_str = locked_file.file_handle().read()
                if cached_creds_str:
                    # Cached credentials metadata dict.
                    cached_creds = json.loads(cached_creds_str)
                    if creds['svc_acct_name'] == cached_creds['svc_acct_name']:
                        if creds['scopes'] in (None, cached_creds['scopes']):
                            scopes = cached_creds['scopes']
            finally:
                locked_file.unlock_and_close()
        return scopes

    def _WriteCacheFile(self, cache_filename, scopes):
        """Writes the credential metadata to the cache file.

        This does not save the credentials themselves (CredentialStore class
        optionally handles that after this class is initialized).

        Args:
          cache_filename: Cache filename to check.
          scopes: Scopes for the desired credentials.
        """
        if _EnsureFileExists(cache_filename):
            locked_file = oauth2client.locked_file.LockedFile(
                cache_filename, 'r+b', 'rb')
            try:
                locked_file.open_and_lock()
                if locked_file.is_locked():
                    creds = {  # Credentials metadata dict.
                        'scopes': sorted(list(scopes)),
                        'svc_acct_name': self.__service_account_name}
                    locked_file.file_handle().write(
                        json.dumps(creds, encoding='ascii'))
                    # If it's not locked, the locking process will
                    # write the same data to the file, so just
                    # continue.
            finally:
                locked_file.unlock_and_close()

    def _ScopesFromMetadataServer(self, scopes):
        if not util.DetectGce():
            raise exceptions.ResourceUnavailableError(
                'GCE credentials requested outside a GCE instance')
        if not self.GetServiceAccount(self.__service_account_name):
            raise exceptions.ResourceUnavailableError(
                'GCE credentials requested but service account '
                '%s does not exist.' % self.__service_account_name)
        if scopes:
            scope_ls = util.NormalizeScopes(scopes)
            instance_scopes = self.GetInstanceScopes()
            if scope_ls > instance_scopes:
                raise exceptions.CredentialsError(
                    'Instance did not have access to scopes %s' % (
                        sorted(list(scope_ls - instance_scopes)),))
        else:
            scopes = self.GetInstanceScopes()
        return scopes

    def GetServiceAccount(self, account):
        account_uri = (
            'http://metadata.google.internal/computeMetadata/'
            'v1/instance/service-accounts')
        additional_headers = {'X-Google-Metadata-Request': 'True'}
        request = urllib.request.Request(
            account_uri, headers=additional_headers)
        try:
            response = _OpenNoProxy(request)
        except urllib.error.URLError as e:
            raise exceptions.CommunicationError(
                'Could not reach metadata service: %s' % e.reason)
        response_lines = [line.rstrip('/\n\r')
                          for line in response.readlines()]
        return account in response_lines

    def GetInstanceScopes(self):
        # Extra header requirement can be found here:
        # https://developers.google.com/compute/docs/metadata
        scopes_uri = (
            'http://metadata.google.internal/computeMetadata/v1/instance/'
            'service-accounts/%s/scopes') % self.__service_account_name
        additional_headers = {'X-Google-Metadata-Request': 'True'}
        request = urllib.request.Request(
            scopes_uri, headers=additional_headers)
        try:
            response = _OpenNoProxy(request)
        except urllib.error.URLError as e:
            raise exceptions.CommunicationError(
                'Could not reach metadata service: %s' % e.reason)
        return util.NormalizeScopes(scope.strip()
                                    for scope in response.readlines())

    def _refresh(self, do_request):
        """Refresh self.access_token.

        This function replaces AppAssertionCredentials._refresh, which
        does not use the credential store and is therefore poorly
        suited for multi-threaded scenarios.

        Args:
          do_request: A function matching httplib2.Http.request's signature.

        """
        # pylint: disable=protected-access
        oauth2client.client.OAuth2Credentials._refresh(self, do_request)
        # pylint: enable=protected-access

    def _do_refresh_request(self, unused_http_request):
        """Refresh self.access_token by querying the metadata server.

        If self.store is initialized, store acquired credentials there.
        """
        token_uri = (
            'http://metadata.google.internal/computeMetadata/v1/instance/'
            'service-accounts/%s/token') % self.__service_account_name
        extra_headers = {'X-Google-Metadata-Request': 'True'}
        request = urllib.request.Request(token_uri, headers=extra_headers)
        try:
            content = _OpenNoProxy(request).read()
        except urllib.error.URLError as e:
            self.invalid = True
            if self.store:
                self.store.locked_put(self)
            raise exceptions.CommunicationError(
                'Could not reach metadata service: %s' % e.reason)
        try:
            credential_info = json.loads(content)
        except ValueError:
            raise exceptions.CredentialsError(
                'Invalid credentials response: uri %s' % token_uri)

        self.access_token = credential_info['access_token']
        if 'expires_in' in credential_info:
            expires_in = int(credential_info['expires_in'])
            self.token_expiry = (
                datetime.timedelta(seconds=expires_in) +
                datetime.datetime.utcnow())
        else:
            self.token_expiry = None
        self.invalid = False
        if self.store:
            self.store.locked_put(self)

    @classmethod
    def from_json(cls, json_data):
        data = json.loads(json_data)
        credentials = GceAssertionCredentials(scopes=[data['scope']])
        if 'access_token' in data:
            credentials.access_token = data['access_token']
        if 'token_expiry' in data:
            credentials.token_expiry = datetime.datetime.strptime(
                data['token_expiry'], oauth2client.client.EXPIRY_FORMAT)
        if 'invalid' in data:
            credentials.invalid = data['invalid']
        return credentials

    @property
    def serialization_data(self):
        raise NotImplementedError(
            'Cannot serialize credentials for GCE service accounts.')


# TODO(craigcitro): Currently, we can't even *load*
# `oauth2client.appengine` without being on appengine, because of how
# it handles imports. Fix that by splitting that module into
# GAE-specific and GAE-independent bits, and guarding imports.
class GaeAssertionCredentials(oauth2client.client.AssertionCredentials):

    """Assertion credentials for Google App Engine apps."""

    def __init__(self, scopes, **kwds):
        if not util.DetectGae():
            raise exceptions.ResourceUnavailableError(
                'GCE credentials requested outside a GCE instance')
        self._scopes = list(util.NormalizeScopes(scopes))
        super(GaeAssertionCredentials, self).__init__(None, **kwds)

    @classmethod
    def Get(cls, *args, **kwds):
        try:
            return cls(*args, **kwds)
        except exceptions.Error:
            return None

    @classmethod
    def from_json(cls, json_data):
        data = json.loads(json_data)
        return GaeAssertionCredentials(data['_scopes'])

    def _refresh(self, _):
        """Refresh self.access_token.

        Args:
          _: (ignored) A function matching httplib2.Http.request's signature.
        """
        from google.appengine.api import app_identity
        try:
            token, _ = app_identity.get_access_token(self._scopes)
        except app_identity.Error as e:
            raise exceptions.CredentialsError(str(e))
        self.access_token = token


def _GetRunFlowFlags(args=None):
    # There's one rare situation where gsutil will not have argparse
    # available, but doesn't need anything depending on argparse anyway,
    # since they're bringing their own credentials. So we just allow this
    # to fail with an ImportError in those cases.
    #
    # TODO(craigcitro): Move this import back to the top when we drop
    # python 2.6 support (eg when gsutil does).
    import argparse

    parser = argparse.ArgumentParser(parents=[tools.argparser])
    # Get command line argparse flags.
    flags = parser.parse_args(args=args)

    # Allow `gflags` and `argparse` to be used side-by-side.
    if hasattr(FLAGS, 'auth_host_name'):
        flags.auth_host_name = FLAGS.auth_host_name
    if hasattr(FLAGS, 'auth_host_port'):
        flags.auth_host_port = FLAGS.auth_host_port
    if hasattr(FLAGS, 'auth_local_webserver'):
        flags.noauth_local_webserver = (not FLAGS.auth_local_webserver)
    return flags


# TODO(craigcitro): Switch this from taking a path to taking a stream.
def CredentialsFromFile(path, client_info):
    """Read credentials from a file."""
    credential_store = oauth2client.multistore_file.get_credential_storage(
        path,
        client_info['client_id'],
        client_info['user_agent'],
        client_info['scope'])
    if hasattr(FLAGS, 'auth_local_webserver'):
        FLAGS.auth_local_webserver = False
    credentials = credential_store.get()
    if credentials is None or credentials.invalid:
        print('Generating new OAuth credentials ...')
        while True:
            # If authorization fails, we want to retry, rather than let this
            # cascade up and get caught elsewhere. If users want out of the
            # retry loop, they can ^C.
            try:
                flow = oauth2client.client.OAuth2WebServerFlow(**client_info)
                flags = _GetRunFlowFlags()
                credentials = tools.run_flow(flow, credential_store, flags)
                break
            except (oauth2client.client.FlowExchangeError, SystemExit) as e:
                # Here SystemExit is "no credential at all", and the
                # FlowExchangeError is "invalid" -- usually because you reused
                # a token.
                print('Invalid authorization: %s' % (e,))
            except httplib2.HttpLib2Error as e:
                print('Communication error: %s' % (e,))
                raise exceptions.CredentialsError(
                    'Communication error creating credentials: %s' % e)
    return credentials


# TODO(craigcitro): Push this into oauth2client.
def GetUserinfo(credentials, http=None):  # pylint: disable=invalid-name
    """Get the userinfo associated with the given credentials.

    This is dependent on the token having either the userinfo.email or
    userinfo.profile scope for the given token.

    Args:
      credentials: (oauth2client.client.Credentials) incoming credentials
      http: (httplib2.Http, optional) http instance to use

    Returns:
      The email address for this token, or None if the required scopes
      aren't available.
    """
    http = http or httplib2.Http()
    url_root = 'https://www.googleapis.com/oauth2/v2/tokeninfo'
    query_args = {'access_token': credentials.access_token}
    url = '?'.join((url_root, urllib.parse.urlencode(query_args)))
    # We ignore communication woes here (i.e. SSL errors, socket
    # timeout), as handling these should be done in a common location.
    response, content = http.request(url)
    if response.status == http_client.BAD_REQUEST:
        credentials.refresh(http)
        response, content = http.request(url)
    return json.loads(content or '{}')  # Save ourselves from an empty reply.
