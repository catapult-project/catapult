# -*- coding: utf-8 -*-
# Copyright 2013 Google Inc. All Rights Reserved.
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
"""This module provides the notification command to gsutil."""

from __future__ import absolute_import

import getopt
import uuid

from gslib.cloud_api import AccessDeniedException
from gslib.command import Command
from gslib.command import NO_MAX
from gslib.command_argument import CommandArgument
from gslib.cs_api_map import ApiSelector
from gslib.exception import CommandException
from gslib.help_provider import CreateHelpText
from gslib.storage_url import StorageUrlFromString


_WATCHBUCKET_SYNOPSIS = """
  gsutil notification watchbucket [-i id] [-t token] app_url bucket_url...
"""

_STOPCHANNEL_SYNOPSIS = """
  gsutil notification stopchannel channel_id resource_id
"""

_SYNOPSIS = _WATCHBUCKET_SYNOPSIS + _STOPCHANNEL_SYNOPSIS.lstrip('\n')

_WATCHBUCKET_DESCRIPTION = """
<B>WATCHBUCKET</B>
  The watchbucket sub-command can be used to watch a bucket for object changes.
  A service account must be used when running this command.

  The app_url parameter must be an HTTPS URL to an application that will be
  notified of changes to any object in the bucket. The URL endpoint must be
  a verified domain on your project. See
  `Notification Authorization <https://developers.google.com/storage/docs/object-change-notification#_Authorization>`_
  for details.

  The optional id parameter can be used to assign a unique identifier to the
  created notification channel. If not provided, a random UUID string will be
  generated.

  The optional token parameter can be used to validate notifications events.
  To do this, set this custom token and store it to later verify that
  notification events contain the client token you expect.

"""

_STOPCHANNEL_DESCRIPTION = """
<B>STOPCHANNEL</B>
  The stopchannel sub-command can be used to stop sending change events to a
  notification channel.

  The channel_id and resource_id parameters should match the values from the
  response of a bucket watch request.

"""

_DESCRIPTION = """
  The notification command can be used to configure notifications.
  For more information on the Object Change Notification feature, please see:
  https://developers.google.com/storage/docs/object-change-notification

  The notification command has two sub-commands:
""" + _WATCHBUCKET_DESCRIPTION + _STOPCHANNEL_DESCRIPTION + """

<B>EXAMPLES</B>

  Watch the bucket example-bucket for changes and send notifications to an
  application server running at example.com:

    gsutil notification watchbucket https://example.com/notify \\
      gs://example-bucket

  Assign identifier my-channel-id to the created notification channel:

    gsutil notification watchbucket -i my-channel-id \\
      https://example.com/notify gs://example-bucket

  Set a custom client token that will be included with each notification event:

    gsutil notification watchbucket -t my-client-token \\
      https://example.com/notify gs://example-bucket

  Stop the notification event channel with channel identifier channel1 and
  resource identifier SoGqan08XDIFWr1Fv_nGpRJBHh8:

    gsutil notification stopchannel channel1 SoGqan08XDIFWr1Fv_nGpRJBHh8

<B>NOTIFICATIONS AND PARALLEL COMPOSITE UPLOADS</B>

  By default, gsutil enables parallel composite uploads for large files (see
  "gsutil help cp"), which means that an upload of a large object can result
  in multiple temporary component objects being uploaded before the actual
  intended object is created. Any subscriber to notifications for this bucket
  will then see a notification for each of these components being created and
  deleted. If this is a concern for you, note that parallel composite uploads
  can be disabled by setting "parallel_composite_upload_threshold = 0" in your
  boto config file.

"""

NOTIFICATION_AUTHORIZATION_FAILED_MESSAGE = """
Watch bucket attempt failed:
  {watch_error}

You attempted to watch a bucket with an application URL of:

  {watch_url}

which is not authorized for your project. Please ensure that you are using
Service Account authentication and that the Service Account's project is
authorized for the application URL. Notification endpoint URLs must also be
whitelisted in your Cloud Console project. To do that, the domain must also be
verified using Google Webmaster Tools. For instructions, please see:

  https://developers.google.com/storage/docs/object-change-notification#_Authorization
"""

_DETAILED_HELP_TEXT = CreateHelpText(_SYNOPSIS, _DESCRIPTION)

_watchbucket_help_text = (
    CreateHelpText(_WATCHBUCKET_SYNOPSIS, _WATCHBUCKET_DESCRIPTION))
_stopchannel_help_text = (
    CreateHelpText(_STOPCHANNEL_SYNOPSIS, _STOPCHANNEL_DESCRIPTION))


class NotificationCommand(Command):
  """Implementation of gsutil notification command."""

  # Command specification. See base class for documentation.
  command_spec = Command.CreateCommandSpec(
      'notification',
      command_name_aliases=[
          'notify', 'notifyconfig', 'notifications', 'notif'],
      usage_synopsis=_SYNOPSIS,
      min_args=3,
      max_args=NO_MAX,
      supported_sub_args='i:t:',
      file_url_ok=False,
      provider_url_ok=False,
      urls_start_arg=1,
      gs_api_support=[ApiSelector.JSON],
      gs_default_api=ApiSelector.JSON,
      argparse_arguments={
          'watchbucket': [
              CommandArgument.MakeFreeTextArgument(),
              CommandArgument.MakeZeroOrMoreCloudBucketURLsArgument()
          ],
          'stopchannel': []
      }
  )
  # Help specification. See help_provider.py for documentation.
  help_spec = Command.HelpSpec(
      help_name='notification',
      help_name_aliases=['watchbucket', 'stopchannel', 'notifyconfig'],
      help_type='command_help',
      help_one_line_summary='Configure object change notification',
      help_text=_DETAILED_HELP_TEXT,
      subcommand_help_text={'watchbucket': _watchbucket_help_text,
                            'stopchannel': _stopchannel_help_text},
  )

  def _WatchBucket(self):
    """Creates a watch on a bucket given in self.args."""
    self.CheckArguments()
    identifier = None
    client_token = None
    if self.sub_opts:
      for o, a in self.sub_opts:
        if o == '-i':
          identifier = a
        if o == '-t':
          client_token = a

    identifier = identifier or str(uuid.uuid4())
    watch_url = self.args[0]
    bucket_arg = self.args[-1]

    if not watch_url.lower().startswith('https://'):
      raise CommandException('The application URL must be an https:// URL.')

    bucket_url = StorageUrlFromString(bucket_arg)
    if not (bucket_url.IsBucket() and bucket_url.scheme == 'gs'):
      raise CommandException(
          'The %s command can only be used with gs:// bucket URLs.' %
          self.command_name)
    if not bucket_url.IsBucket():
      raise CommandException('URL must name a bucket for the %s command.' %
                             self.command_name)

    self.logger.info('Watching bucket %s with application URL %s ...',
                     bucket_url, watch_url)

    try:
      channel = self.gsutil_api.WatchBucket(
          bucket_url.bucket_name, watch_url, identifier, token=client_token,
          provider=bucket_url.scheme)
    except AccessDeniedException, e:
      self.logger.warn(NOTIFICATION_AUTHORIZATION_FAILED_MESSAGE.format(
          watch_error=str(e), watch_url=watch_url))
      raise

    channel_id = channel.id
    resource_id = channel.resourceId
    client_token = channel.token
    self.logger.info('Successfully created watch notification channel.')
    self.logger.info('Watch channel identifier: %s', channel_id)
    self.logger.info('Canonicalized resource identifier: %s', resource_id)
    self.logger.info('Client state token: %s', client_token)

    return 0

  def _StopChannel(self):
    channel_id = self.args[0]
    resource_id = self.args[1]

    self.logger.info('Removing channel %s with resource identifier %s ...',
                     channel_id, resource_id)
    self.gsutil_api.StopChannel(channel_id, resource_id, provider='gs')
    self.logger.info('Succesfully removed channel.')

    return 0

  def _RunSubCommand(self, func):
    try:
      (self.sub_opts, self.args) = getopt.getopt(
          self.args, self.command_spec.supported_sub_args)
      return func()
    except getopt.GetoptError, e:
      self.RaiseInvalidArgumentException()

  def RunCommand(self):
    """Command entry point for the notification command."""
    subcommand = self.args.pop(0)

    if subcommand == 'watchbucket':
      return self._RunSubCommand(self._WatchBucket)
    elif subcommand == 'stopchannel':
      return self._RunSubCommand(self._StopChannel)
    else:
      raise CommandException('Invalid subcommand "%s" for the %s command.' %
                             (subcommand, self.command_name))
