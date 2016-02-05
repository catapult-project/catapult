# -*- coding: utf-8 -*-
# Copyright 2010 Google Inc. All Rights Reserved.
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
"""Base class for gsutil commands.

In addition to base class code, this file contains helpers that depend on base
class state (such as GetAndPrintAcl) In general, functions that depend on
class state and that are used by multiple commands belong in this file.
Functions that don't depend on class state belong in util.py, and non-shared
helpers belong in individual subclasses.
"""

from __future__ import absolute_import

import codecs
from collections import namedtuple
import copy
import getopt
import logging
import multiprocessing
import os
import Queue
import signal
import sys
import textwrap
import threading
import traceback

import boto
from boto.storage_uri import StorageUri
import gslib
from gslib.cloud_api import AccessDeniedException
from gslib.cloud_api import ArgumentException
from gslib.cloud_api import ServiceException
from gslib.cloud_api_delegator import CloudApiDelegator
from gslib.cs_api_map import ApiSelector
from gslib.cs_api_map import GsutilApiMapFactory
from gslib.exception import CommandException
from gslib.help_provider import HelpProvider
from gslib.name_expansion import NameExpansionIterator
from gslib.name_expansion import NameExpansionResult
from gslib.parallelism_framework_util import AtomicDict
from gslib.plurality_checkable_iterator import PluralityCheckableIterator
from gslib.sig_handling import RegisterSignalHandler
from gslib.storage_url import StorageUrlFromString
from gslib.third_party.storage_apitools import storage_v1_messages as apitools_messages
from gslib.translation_helper import AclTranslation
from gslib.translation_helper import PRIVATE_DEFAULT_OBJ_ACL
from gslib.util import CheckMultiprocessingAvailableAndInit
from gslib.util import GetConfigFilePath
from gslib.util import GsutilStreamHandler
from gslib.util import HaveFileUrls
from gslib.util import HaveProviderUrls
from gslib.util import IS_WINDOWS
from gslib.util import NO_MAX
from gslib.util import UrlsAreForSingleProvider
from gslib.util import UTF8
from gslib.wildcard_iterator import CreateWildcardIterator

OFFER_GSUTIL_M_SUGGESTION_THRESHOLD = 5

if IS_WINDOWS:
  import ctypes  # pylint: disable=g-import-not-at-top


def _DefaultExceptionHandler(cls, e):
  cls.logger.exception(e)


def CreateGsutilLogger(command_name):
  """Creates a logger that resembles 'print' output.

  This logger abides by gsutil -d/-D/-DD/-q options.

  By default (if none of the above options is specified) the logger will display
  all messages logged with level INFO or above. Log propagation is disabled.

  Args:
    command_name: Command name to create logger for.

  Returns:
    A logger object.
  """
  log = logging.getLogger(command_name)
  log.propagate = False
  log.setLevel(logging.root.level)
  log_handler = GsutilStreamHandler()
  log_handler.setFormatter(logging.Formatter('%(message)s'))
  # Commands that call other commands (like mv) would cause log handlers to be
  # added more than once, so avoid adding if one is already present.
  if not log.handlers:
    log.addHandler(log_handler)
  return log


def _UrlArgChecker(command_instance, url):
  if not command_instance.exclude_symlinks:
    return True
  exp_src_url = url.expanded_storage_url
  if exp_src_url.IsFileUrl() and os.path.islink(exp_src_url.object_name):
    command_instance.logger.info('Skipping symbolic link %s...', exp_src_url)
    return False
  return True


def DummyArgChecker(*unused_args):
  return True


def SetAclFuncWrapper(cls, name_expansion_result, thread_state=None):
  return cls.SetAclFunc(name_expansion_result, thread_state=thread_state)


def SetAclExceptionHandler(cls, e):
  """Exception handler that maintains state about post-completion status."""
  cls.logger.error(str(e))
  cls.everything_set_okay = False

# We will keep this list of all thread- or process-safe queues ever created by
# the main thread so that we can forcefully kill them upon shutdown. Otherwise,
# we encounter a Python bug in which empty queues block forever on join (which
# is called as part of the Python exit function cleanup) under the impression
# that they are non-empty.
# However, this also lets us shut down somewhat more cleanly when interrupted.
queues = []


def _NewMultiprocessingQueue():
  queue = multiprocessing.Queue(MAX_QUEUE_SIZE)
  queues.append(queue)
  return queue


def _NewThreadsafeQueue():
  queue = Queue.Queue(MAX_QUEUE_SIZE)
  queues.append(queue)
  return queue

# The maximum size of a process- or thread-safe queue. Imposing this limit
# prevents us from needing to hold an arbitrary amount of data in memory.
# However, setting this number too high (e.g., >= 32768 on OS X) can cause
# problems on some operating systems.
MAX_QUEUE_SIZE = 32500

# That maximum depth of the tree of recursive calls to command.Apply. This is
# an arbitrary limit put in place to prevent developers from accidentally
# causing problems with infinite recursion, and it can be increased if needed.
MAX_RECURSIVE_DEPTH = 5

ZERO_TASKS_TO_DO_ARGUMENT = ('There were no', 'tasks to do')

# Map from deprecated aliases to the current command and subcommands that
# provide the same behavior.
# TODO: Remove this map and deprecate old commands on 9/9/14.
OLD_ALIAS_MAP = {'chacl': ['acl', 'ch'],
                 'getacl': ['acl', 'get'],
                 'setacl': ['acl', 'set'],
                 'getcors': ['cors', 'get'],
                 'setcors': ['cors', 'set'],
                 'chdefacl': ['defacl', 'ch'],
                 'getdefacl': ['defacl', 'get'],
                 'setdefacl': ['defacl', 'set'],
                 'disablelogging': ['logging', 'set', 'off'],
                 'enablelogging': ['logging', 'set', 'on'],
                 'getlogging': ['logging', 'get'],
                 'getversioning': ['versioning', 'get'],
                 'setversioning': ['versioning', 'set'],
                 'getwebcfg': ['web', 'get'],
                 'setwebcfg': ['web', 'set']}


# Declare all of the module level variables - see
# InitializeMultiprocessingVariables for an explanation of why this is
# necessary.
# pylint: disable=global-at-module-level
global manager, consumer_pools, task_queues, caller_id_lock, caller_id_counter
global total_tasks, call_completed_map, global_return_values_map
global need_pool_or_done_cond, caller_id_finished_count, new_pool_needed
global current_max_recursive_level, shared_vars_map, shared_vars_list_map
global class_map, worker_checking_level_lock, failure_count


def InitializeMultiprocessingVariables():
  """Initializes module-level variables that will be inherited by subprocesses.

  On Windows, a multiprocessing.Manager object should only
  be created within an "if __name__ == '__main__':" block. This function
  must be called, otherwise every command that calls Command.Apply will fail.
  """
  # This list of global variables must exactly match the above list of
  # declarations.
  # pylint: disable=global-variable-undefined
  global manager, consumer_pools, task_queues, caller_id_lock, caller_id_counter
  global total_tasks, call_completed_map, global_return_values_map
  global need_pool_or_done_cond, caller_id_finished_count, new_pool_needed
  global current_max_recursive_level, shared_vars_map, shared_vars_list_map
  global class_map, worker_checking_level_lock, failure_count

  manager = multiprocessing.Manager()

  consumer_pools = []

  # List of all existing task queues - used by all pools to find the queue
  # that's appropriate for the given recursive_apply_level.
  task_queues = []

  # Used to assign a globally unique caller ID to each Apply call.
  caller_id_lock = manager.Lock()
  caller_id_counter = multiprocessing.Value('i', 0)

  # Map from caller_id to total number of tasks to be completed for that ID.
  total_tasks = AtomicDict(manager=manager)

  # Map from caller_id to a boolean which is True iff all its tasks are
  # finished.
  call_completed_map = AtomicDict(manager=manager)

  # Used to keep track of the set of return values for each caller ID.
  global_return_values_map = AtomicDict(manager=manager)

  # Condition used to notify any waiting threads that a task has finished or
  # that a call to Apply needs a new set of consumer processes.
  need_pool_or_done_cond = manager.Condition()

  # Lock used to prevent multiple worker processes from asking the main thread
  # to create a new consumer pool for the same level.
  worker_checking_level_lock = manager.Lock()

  # Map from caller_id to the current number of completed tasks for that ID.
  caller_id_finished_count = AtomicDict(manager=manager)

  # Used as a way for the main thread to distinguish between being woken up
  # by another call finishing and being woken up by a call that needs a new set
  # of consumer processes.
  new_pool_needed = multiprocessing.Value('i', 0)

  current_max_recursive_level = multiprocessing.Value('i', 0)

  # Map from (caller_id, name) to the value of that shared variable.
  shared_vars_map = AtomicDict(manager=manager)
  shared_vars_list_map = AtomicDict(manager=manager)

  # Map from caller_id to calling class.
  class_map = manager.dict()

  # Number of tasks that resulted in an exception in calls to Apply().
  failure_count = multiprocessing.Value('i', 0)


def InitializeThreadingVariables():
  """Initializes module-level variables used when running multi-threaded.

  When multiprocessing is not available (or on Windows where only 1 process
  is used), thread-safe analogs to the multiprocessing global variables
  must be initialized. This function is the thread-safe analog to
  InitializeMultiprocessingVariables.
  """
  # pylint: disable=global-variable-undefined
  global global_return_values_map, shared_vars_map, failure_count
  global caller_id_finished_count, shared_vars_list_map, total_tasks
  global need_pool_or_done_cond, call_completed_map, class_map
  global task_queues, caller_id_lock, caller_id_counter
  caller_id_counter = 0
  caller_id_finished_count = AtomicDict()
  caller_id_lock = threading.Lock()
  call_completed_map = AtomicDict()
  class_map = AtomicDict()
  failure_count = 0
  global_return_values_map = AtomicDict()
  need_pool_or_done_cond = threading.Condition()
  shared_vars_list_map = AtomicDict()
  shared_vars_map = AtomicDict()
  task_queues = []
  total_tasks = AtomicDict()


# Each subclass of Command must define a property named 'command_spec' that is
# an instance of the following class.
CommandSpec = namedtuple('CommandSpec', [
    # Name of command.
    'command_name',
    # Usage synopsis.
    'usage_synopsis',
    # List of command name aliases.
    'command_name_aliases',
    # Min number of args required by this command.
    'min_args',
    # Max number of args required by this command, or NO_MAX.
    'max_args',
    # Getopt-style string specifying acceptable sub args.
    'supported_sub_args',
    # True if file URLs are acceptable for this command.
    'file_url_ok',
    # True if provider-only URLs are acceptable for this command.
    'provider_url_ok',
    # Index in args of first URL arg.
    'urls_start_arg',
    # List of supported APIs
    'gs_api_support',
    # Default API to use for this command
    'gs_default_api',
    # Private arguments (for internal testing)
    'supported_private_args',
    'argparse_arguments',
])


class Command(HelpProvider):
  """Base class for all gsutil commands."""

  # Each subclass must override this with an instance of CommandSpec.
  command_spec = None

  _commands_with_subcommands_and_subopts = ['acl', 'defacl', 'logging', 'web',
                                            'notification']

  # This keeps track of the recursive depth of the current call to Apply.
  recursive_apply_level = 0

  # If the multiprocessing module isn't available, we'll use this to keep track
  # of the caller_id.
  sequential_caller_id = -1

  @staticmethod
  def CreateCommandSpec(command_name, usage_synopsis=None,
                        command_name_aliases=None, min_args=0,
                        max_args=NO_MAX, supported_sub_args='',
                        file_url_ok=False, provider_url_ok=False,
                        urls_start_arg=0, gs_api_support=None,
                        gs_default_api=None, supported_private_args=None,
                        argparse_arguments=None):
    """Creates an instance of CommandSpec, with defaults."""
    return CommandSpec(
        command_name=command_name,
        usage_synopsis=usage_synopsis,
        command_name_aliases=command_name_aliases or [],
        min_args=min_args,
        max_args=max_args,
        supported_sub_args=supported_sub_args,
        file_url_ok=file_url_ok,
        provider_url_ok=provider_url_ok,
        urls_start_arg=urls_start_arg,
        gs_api_support=gs_api_support or [ApiSelector.XML],
        gs_default_api=gs_default_api or ApiSelector.XML,
        supported_private_args=supported_private_args,
        argparse_arguments=argparse_arguments or [])

  # Define a convenience property for command name, since it's used many places.
  def _GetDefaultCommandName(self):
    return self.command_spec.command_name
  command_name = property(_GetDefaultCommandName)

  def _CalculateUrlsStartArg(self):
    """Calculate the index in args of the first URL arg.

    Returns:
      Index of the first URL arg (according to the command spec).
    """
    return self.command_spec.urls_start_arg

  def _TranslateDeprecatedAliases(self, args):
    """Map deprecated aliases to the corresponding new command, and warn."""
    new_command_args = OLD_ALIAS_MAP.get(self.command_alias_used, None)
    if new_command_args:
      # Prepend any subcommands for the new command. The command name itself
      # is not part of the args, so leave it out.
      args = new_command_args[1:] + args
      self.logger.warn('\n'.join(textwrap.wrap(
          ('You are using a deprecated alias, "%(used_alias)s", for the '
           '"%(command_name)s" command. This will stop working on 9/9/2014. '
           'Please use "%(command_name)s" with the appropriate sub-command in '
           'the future. See "gsutil help %(command_name)s" for details.') %
          {'used_alias': self.command_alias_used,
           'command_name': self.command_name})))
    return args

  def __init__(self, command_runner, args, headers, debug, trace_token,
               parallel_operations, bucket_storage_uri_class,
               gsutil_api_class_map_factory, logging_filters=None,
               command_alias_used=None):
    """Instantiates a Command.

    Args:
      command_runner: CommandRunner (for commands built atop other commands).
      args: Command-line args (arg0 = actual arg, not command name ala bash).
      headers: Dictionary containing optional HTTP headers to pass to boto.
      debug: Debug level to pass in to boto connection (range 0..3).
      trace_token: Trace token to pass to the API implementation.
      parallel_operations: Should command operations be executed in parallel?
      bucket_storage_uri_class: Class to instantiate for cloud StorageUris.
                                Settable for testing/mocking.
      gsutil_api_class_map_factory: Creates map of cloud storage interfaces.
                                    Settable for testing/mocking.
      logging_filters: Optional list of logging. Filters to apply to this
                       command's logger.
      command_alias_used: The alias that was actually used when running this
                          command (as opposed to the "official" command name,
                          which will always correspond to the file name).

    Implementation note: subclasses shouldn't need to define an __init__
    method, and instead depend on the shared initialization that happens
    here. If you do define an __init__ method in a subclass you'll need to
    explicitly call super().__init__(). But you're encouraged not to do this,
    because it will make changing the __init__ interface more painful.
    """
    # Save class values from constructor params.
    self.command_runner = command_runner
    self.unparsed_args = args
    self.headers = headers
    self.debug = debug
    self.trace_token = trace_token
    self.parallel_operations = parallel_operations
    self.bucket_storage_uri_class = bucket_storage_uri_class
    self.gsutil_api_class_map_factory = gsutil_api_class_map_factory
    self.exclude_symlinks = False
    self.recursion_requested = False
    self.all_versions = False
    self.command_alias_used = command_alias_used

    # Global instance of a threaded logger object.
    self.logger = CreateGsutilLogger(self.command_name)
    if logging_filters:
      for log_filter in logging_filters:
        self.logger.addFilter(log_filter)

    if self.command_spec is None:
      raise CommandException('"%s" command implementation is missing a '
                             'command_spec definition.' % self.command_name)

    # Parse and validate args.
    self.args = self._TranslateDeprecatedAliases(args)
    self.ParseSubOpts()

    # Named tuple public functions start with _
    # pylint: disable=protected-access
    self.command_spec = self.command_spec._replace(
        urls_start_arg=self._CalculateUrlsStartArg())

    if (len(self.args) < self.command_spec.min_args
        or len(self.args) > self.command_spec.max_args):
      self.RaiseWrongNumberOfArgumentsException()

    if self.command_name not in self._commands_with_subcommands_and_subopts:
      self.CheckArguments()

    # Build the support and default maps from the command spec.
    support_map = {
        'gs': self.command_spec.gs_api_support,
        's3': [ApiSelector.XML]
    }
    default_map = {
        'gs': self.command_spec.gs_default_api,
        's3': ApiSelector.XML
    }
    self.gsutil_api_map = GsutilApiMapFactory.GetApiMap(
        self.gsutil_api_class_map_factory, support_map, default_map)

    self.project_id = None
    self.gsutil_api = CloudApiDelegator(
        bucket_storage_uri_class, self.gsutil_api_map,
        self.logger, debug=self.debug, trace_token=self.trace_token)

    # Cross-platform path to run gsutil binary.
    self.gsutil_cmd = ''
    # If running on Windows, invoke python interpreter explicitly.
    if gslib.util.IS_WINDOWS:
      self.gsutil_cmd += 'python '
    # Add full path to gsutil to make sure we test the correct version.
    self.gsutil_path = gslib.GSUTIL_PATH
    self.gsutil_cmd += self.gsutil_path

    # We're treating recursion_requested like it's used by all commands, but
    # only some of the commands accept the -R option.
    if self.sub_opts:
      for o, unused_a in self.sub_opts:
        if o == '-r' or o == '-R':
          self.recursion_requested = True
          break

    self.multiprocessing_is_available = (
        CheckMultiprocessingAvailableAndInit().is_available)

  def RaiseWrongNumberOfArgumentsException(self):
    """Raises exception for wrong number of arguments supplied to command."""
    if len(self.args) < self.command_spec.min_args:
      tail_str = 's' if self.command_spec.min_args > 1 else ''
      message = ('The %s command requires at least %d argument%s.' %
                 (self.command_name, self.command_spec.min_args, tail_str))
    else:
      message = ('The %s command accepts at most %d arguments.' %
                 (self.command_name, self.command_spec.max_args))
    message += ' Usage:\n%s\nFor additional help run:\n  gsutil help %s' % (
        self.command_spec.usage_synopsis, self.command_name)
    raise CommandException(message)

  def RaiseInvalidArgumentException(self):
    """Raises exception for specifying an invalid argument to command."""
    message = ('Incorrect option(s) specified. Usage:\n%s\n'
               'For additional help run:\n  gsutil help %s' % (
                   self.command_spec.usage_synopsis, self.command_name))
    raise CommandException(message)

  def ParseSubOpts(self, check_args=False):
    """Parses sub-opt args.

    Args:
      check_args: True to have CheckArguments() called after parsing.

    Populates:
      (self.sub_opts, self.args) from parsing.

    Raises: RaiseInvalidArgumentException if invalid args specified.
    """
    try:
      self.sub_opts, self.args = getopt.getopt(
          self.args, self.command_spec.supported_sub_args,
          self.command_spec.supported_private_args or [])
    except getopt.GetoptError:
      self.RaiseInvalidArgumentException()
    if check_args:
      self.CheckArguments()

  def CheckArguments(self):
    """Checks that command line arguments match the command_spec.

    Any commands in self._commands_with_subcommands_and_subopts are responsible
    for calling this method after handling initial parsing of their arguments.
    This prevents commands with sub-commands as well as options from breaking
    the parsing of getopt.

    TODO: Provide a function to parse commands and sub-commands more
    intelligently once we stop allowing the deprecated command versions.

    Raises:
      CommandException if the arguments don't match.
    """

    if (not self.command_spec.file_url_ok
        and HaveFileUrls(self.args[self.command_spec.urls_start_arg:])):
      raise CommandException('"%s" command does not support "file://" URLs. '
                             'Did you mean to use a gs:// URL?' %
                             self.command_name)
    if (not self.command_spec.provider_url_ok
        and HaveProviderUrls(self.args[self.command_spec.urls_start_arg:])):
      raise CommandException('"%s" command does not support provider-only '
                             'URLs.' % self.command_name)

  def WildcardIterator(self, url_string, all_versions=False):
    """Helper to instantiate gslib.WildcardIterator.

    Args are same as gslib.WildcardIterator interface, but this method fills in
    most of the values from instance state.

    Args:
      url_string: URL string naming wildcard objects to iterate.
      all_versions: If true, the iterator yields all versions of objects
                    matching the wildcard.  If false, yields just the live
                    object version.

    Returns:
      WildcardIterator for use by caller.
    """
    return CreateWildcardIterator(
        url_string, self.gsutil_api, all_versions=all_versions,
        debug=self.debug, project_id=self.project_id)

  def RunCommand(self):
    """Abstract function in base class. Subclasses must implement this.

    The return value of this function will be used as the exit status of the
    process, so subclass commands should return an integer exit code (0 for
    success, a value in [1,255] for failure).
    """
    raise CommandException('Command %s is missing its RunCommand() '
                           'implementation' % self.command_name)

  ############################################################
  # Shared helper functions that depend on base class state. #
  ############################################################

  def ApplyAclFunc(self, acl_func, acl_excep_handler, url_strs):
    """Sets the standard or default object ACL depending on self.command_name.

    Args:
      acl_func: ACL function to be passed to Apply.
      acl_excep_handler: ACL exception handler to be passed to Apply.
      url_strs: URL strings on which to set ACL.

    Raises:
      CommandException if an ACL could not be set.
    """
    multi_threaded_url_args = []
    # Handle bucket ACL setting operations single-threaded, because
    # our threading machinery currently assumes it's working with objects
    # (name_expansion_iterator), and normally we wouldn't expect users to need
    # to set ACLs on huge numbers of buckets at once anyway.
    for url_str in url_strs:
      url = StorageUrlFromString(url_str)
      if url.IsCloudUrl() and url.IsBucket():
        if self.recursion_requested:
          # If user specified -R option, convert any bucket args to bucket
          # wildcards (e.g., gs://bucket/*), to prevent the operation from
          # being applied to the buckets themselves.
          url.object_name = '*'
          multi_threaded_url_args.append(url.url_string)
        else:
          # Convert to a NameExpansionResult so we can re-use the threaded
          # function for the single-threaded implementation.  RefType is unused.
          for blr in self.WildcardIterator(url.url_string).IterBuckets(
              bucket_fields=['id']):
            name_expansion_for_url = NameExpansionResult(
                url, False, False, blr.storage_url)
            acl_func(self, name_expansion_for_url)
      else:
        multi_threaded_url_args.append(url_str)

    if len(multi_threaded_url_args) >= 1:
      name_expansion_iterator = NameExpansionIterator(
          self.command_name, self.debug,
          self.logger, self.gsutil_api,
          multi_threaded_url_args, self.recursion_requested,
          all_versions=self.all_versions,
          continue_on_error=self.continue_on_error or self.parallel_operations)

      # Perform requests in parallel (-m) mode, if requested, using
      # configured number of parallel processes and threads. Otherwise,
      # perform requests with sequential function calls in current process.
      self.Apply(acl_func, name_expansion_iterator, acl_excep_handler,
                 fail_on_error=not self.continue_on_error)

    if not self.everything_set_okay and not self.continue_on_error:
      raise CommandException('ACLs for some objects could not be set.')

  def SetAclFunc(self, name_expansion_result, thread_state=None):
    """Sets the object ACL for the name_expansion_result provided.

    Args:
      name_expansion_result: NameExpansionResult describing the target object.
      thread_state: If present, use this gsutil Cloud API instance for the set.
    """
    if thread_state:
      assert not self.def_acl
      gsutil_api = thread_state
    else:
      gsutil_api = self.gsutil_api
    op_string = 'default object ACL' if self.def_acl else 'ACL'
    url = name_expansion_result.expanded_storage_url
    self.logger.info('Setting %s on %s...', op_string, url)
    if (gsutil_api.GetApiSelector(url.scheme) == ApiSelector.XML
        and url.scheme != 'gs'):
      # If we are called with a non-google ACL model, we need to use the XML
      # passthrough. acl_arg should either be a canned ACL or an XML ACL.
      self._SetAclXmlPassthrough(url, gsutil_api)
    else:
      # Normal Cloud API path. acl_arg is a JSON ACL or a canned ACL.
      self._SetAclGsutilApi(url, gsutil_api)

  def _SetAclXmlPassthrough(self, url, gsutil_api):
    """Sets the ACL for the URL provided using the XML passthrough functions.

    This function assumes that self.def_acl, self.canned,
    and self.continue_on_error are initialized, and that self.acl_arg is
    either an XML string or a canned ACL string.

    Args:
      url: CloudURL to set the ACL on.
      gsutil_api: gsutil Cloud API to use for the ACL set. Must support XML
          passthrough functions.
    """
    try:
      orig_prefer_api = gsutil_api.prefer_api
      gsutil_api.prefer_api = ApiSelector.XML
      gsutil_api.XmlPassThroughSetAcl(
          self.acl_arg, url, canned=self.canned,
          def_obj_acl=self.def_acl, provider=url.scheme)
    except ServiceException as e:
      if self.continue_on_error:
        self.everything_set_okay = False
        self.logger.error(e)
      else:
        raise
    finally:
      gsutil_api.prefer_api = orig_prefer_api

  def _SetAclGsutilApi(self, url, gsutil_api):
    """Sets the ACL for the URL provided using the gsutil Cloud API.

    This function assumes that self.def_acl, self.canned,
    and self.continue_on_error are initialized, and that self.acl_arg is
    either a JSON string or a canned ACL string.

    Args:
      url: CloudURL to set the ACL on.
      gsutil_api: gsutil Cloud API to use for the ACL set.
    """
    try:
      if url.IsBucket():
        if self.def_acl:
          if self.canned:
            gsutil_api.PatchBucket(
                url.bucket_name, apitools_messages.Bucket(),
                canned_def_acl=self.acl_arg, provider=url.scheme, fields=['id'])
          else:
            def_obj_acl = AclTranslation.JsonToMessage(
                self.acl_arg, apitools_messages.ObjectAccessControl)
            if not def_obj_acl:
              # Use a sentinel value to indicate a private (no entries) default
              # object ACL.
              def_obj_acl.append(PRIVATE_DEFAULT_OBJ_ACL)
            bucket_metadata = apitools_messages.Bucket(
                defaultObjectAcl=def_obj_acl)
            gsutil_api.PatchBucket(url.bucket_name, bucket_metadata,
                                   provider=url.scheme, fields=['id'])
        else:
          if self.canned:
            gsutil_api.PatchBucket(
                url.bucket_name, apitools_messages.Bucket(),
                canned_acl=self.acl_arg, provider=url.scheme, fields=['id'])
          else:
            bucket_acl = AclTranslation.JsonToMessage(
                self.acl_arg, apitools_messages.BucketAccessControl)
            bucket_metadata = apitools_messages.Bucket(acl=bucket_acl)
            gsutil_api.PatchBucket(url.bucket_name, bucket_metadata,
                                   provider=url.scheme, fields=['id'])
      else:  # url.IsObject()
        if self.canned:
          gsutil_api.PatchObjectMetadata(
              url.bucket_name, url.object_name, apitools_messages.Object(),
              provider=url.scheme, generation=url.generation,
              canned_acl=self.acl_arg)
        else:
          object_acl = AclTranslation.JsonToMessage(
              self.acl_arg, apitools_messages.ObjectAccessControl)
          object_metadata = apitools_messages.Object(acl=object_acl)
          gsutil_api.PatchObjectMetadata(url.bucket_name, url.object_name,
                                         object_metadata, provider=url.scheme,
                                         generation=url.generation)
    except ArgumentException, e:
      raise
    except ServiceException, e:
      if self.continue_on_error:
        self.everything_set_okay = False
        self.logger.error(e)
      else:
        raise

  def SetAclCommandHelper(self, acl_func, acl_excep_handler):
    """Sets ACLs on the self.args using the passed-in acl function.

    Args:
      acl_func: ACL function to be passed to Apply.
      acl_excep_handler: ACL exception handler to be passed to Apply.
    """
    acl_arg = self.args[0]
    url_args = self.args[1:]
    # Disallow multi-provider setacl requests, because there are differences in
    # the ACL models.
    if not UrlsAreForSingleProvider(url_args):
      raise CommandException('"%s" command spanning providers not allowed.' %
                             self.command_name)

    # Determine whether acl_arg names a file containing XML ACL text vs. the
    # string name of a canned ACL.
    if os.path.isfile(acl_arg):
      with codecs.open(acl_arg, 'r', UTF8) as f:
        acl_arg = f.read()
      self.canned = False
    else:
      # No file exists, so expect a canned ACL string.
      # validate=False because we allow wildcard urls.
      storage_uri = boto.storage_uri(
          url_args[0], debug=self.debug, validate=False,
          bucket_storage_uri_class=self.bucket_storage_uri_class)

      canned_acls = storage_uri.canned_acls()
      if acl_arg not in canned_acls:
        raise CommandException('Invalid canned ACL "%s".' % acl_arg)
      self.canned = True

    # Used to track if any ACLs failed to be set.
    self.everything_set_okay = True
    self.acl_arg = acl_arg

    self.ApplyAclFunc(acl_func, acl_excep_handler, url_args)
    if not self.everything_set_okay and not self.continue_on_error:
      raise CommandException('ACLs for some objects could not be set.')

  def _WarnServiceAccounts(self):
    """Warns service account users who have received an AccessDenied error.

    When one of the metadata-related commands fails due to AccessDenied, user
    must ensure that they are listed as an Owner in the API console.
    """
    # Import this here so that the value will be set first in
    # gcs_oauth2_boto_plugin.
    # pylint: disable=g-import-not-at-top
    from gcs_oauth2_boto_plugin.oauth2_plugin import IS_SERVICE_ACCOUNT

    if IS_SERVICE_ACCOUNT:
      # This method is only called when canned ACLs are used, so the warning
      # definitely applies.
      self.logger.warning('\n'.join(textwrap.wrap(
          'It appears that your service account has been denied access while '
          'attempting to perform a metadata operation. If you believe that you '
          'should have access to this metadata (i.e., if it is associated with '
          'your account), please make sure that your service account''s email '
          'address is listed as an Owner in the Team tab of the API console. '
          'See "gsutil help creds" for further information.\n')))

  def GetAndPrintAcl(self, url_str):
    """Prints the standard or default object ACL depending on self.command_name.

    Args:
      url_str: URL string to get ACL for.
    """
    blr = self.GetAclCommandBucketListingReference(url_str)
    url = StorageUrlFromString(url_str)
    if (self.gsutil_api.GetApiSelector(url.scheme) == ApiSelector.XML
        and url.scheme != 'gs'):
      # Need to use XML passthrough.
      try:
        acl = self.gsutil_api.XmlPassThroughGetAcl(
            url, def_obj_acl=self.def_acl, provider=url.scheme)
        print acl.to_xml()
      except AccessDeniedException, _:
        self._WarnServiceAccounts()
        raise
    else:
      if self.command_name == 'defacl':
        acl = blr.root_object.defaultObjectAcl
        if not acl:
          self.logger.warn(
              'No default object ACL present for %s. This could occur if '
              'the default object ACL is private, in which case objects '
              'created in this bucket will be readable only by their '
              'creators. It could also mean you do not have OWNER permission '
              'on %s and therefore do not have permission to read the '
              'default object ACL.', url_str, url_str)
      else:
        acl = blr.root_object.acl
        if not acl:
          self._WarnServiceAccounts()
          raise AccessDeniedException('Access denied. Please ensure you have '
                                      'OWNER permission on %s.' % url_str)
      print AclTranslation.JsonFromMessage(acl)

  def GetAclCommandBucketListingReference(self, url_str):
    """Gets a single bucket listing reference for an acl get command.

    Args:
      url_str: URL string to get the bucket listing reference for.

    Returns:
      BucketListingReference for the URL string.

    Raises:
      CommandException if string did not result in exactly one reference.
    """
    # We're guaranteed by caller that we have the appropriate type of url
    # string for the call (ex. we will never be called with an object string
    # by getdefacl)
    wildcard_url = StorageUrlFromString(url_str)
    if wildcard_url.IsObject():
      plurality_iter = PluralityCheckableIterator(
          self.WildcardIterator(url_str).IterObjects(
              bucket_listing_fields=['acl']))
    else:
      # Bucket or provider.  We call IterBuckets explicitly here to ensure that
      # the root object is populated with the acl.
      if self.command_name == 'defacl':
        bucket_fields = ['defaultObjectAcl']
      else:
        bucket_fields = ['acl']
      plurality_iter = PluralityCheckableIterator(
          self.WildcardIterator(url_str).IterBuckets(
              bucket_fields=bucket_fields))
    if plurality_iter.IsEmpty():
      raise CommandException('No URLs matched')
    if plurality_iter.HasPlurality():
      raise CommandException(
          '%s matched more than one URL, which is not allowed by the %s '
          'command' % (url_str, self.command_name))
    return list(plurality_iter)[0]

  def _HandleMultiProcessingSigs(self, signal_num, unused_cur_stack_frame):
    """Handles signals INT AND TERM during a multi-process/multi-thread request.

    Kills subprocesses.

    Args:
      unused_signal_num: signal generated by ^C.
      unused_cur_stack_frame: Current stack frame.
    """
    # Note: This only works under Linux/MacOS. See
    # https://github.com/GoogleCloudPlatform/gsutil/issues/99 for details
    # about why making it work correctly across OS's is harder and still open.
    ShutDownGsutil()
    if signal_num == signal.SIGINT:
      sys.stderr.write('Caught ^C - exiting\n')
    # Simply calling sys.exit(1) doesn't work - see above bug for details.
    KillProcess(os.getpid())

  def GetSingleBucketUrlFromArg(self, arg, bucket_fields=None):
    """Gets a single bucket URL based on the command arguments.

    Args:
      arg: String argument to get bucket URL for.
      bucket_fields: Fields to populate for the bucket.

    Returns:
      (StorageUrl referring to a single bucket, Bucket metadata).

    Raises:
      CommandException if args did not match exactly one bucket.
    """
    plurality_checkable_iterator = self.GetBucketUrlIterFromArg(
        arg, bucket_fields=bucket_fields)
    if plurality_checkable_iterator.HasPlurality():
      raise CommandException(
          '%s matched more than one URL, which is not\n'
          'allowed by the %s command' % (arg, self.command_name))
    blr = list(plurality_checkable_iterator)[0]
    return StorageUrlFromString(blr.url_string), blr.root_object

  def GetBucketUrlIterFromArg(self, arg, bucket_fields=None):
    """Gets a single bucket URL based on the command arguments.

    Args:
      arg: String argument to iterate over.
      bucket_fields: Fields to populate for the bucket.

    Returns:
      PluralityCheckableIterator over buckets.

    Raises:
      CommandException if iterator matched no buckets.
    """
    arg_url = StorageUrlFromString(arg)
    if not arg_url.IsCloudUrl() or arg_url.IsObject():
      raise CommandException('"%s" command must specify a bucket' %
                             self.command_name)

    plurality_checkable_iterator = PluralityCheckableIterator(
        self.WildcardIterator(arg).IterBuckets(
            bucket_fields=bucket_fields))
    if plurality_checkable_iterator.IsEmpty():
      raise CommandException('No URLs matched')
    return plurality_checkable_iterator

  ######################
  # Private functions. #
  ######################

  def _ResetConnectionPool(self):
    # Each OS process needs to establish its own set of connections to
    # the server to avoid writes from different OS processes interleaving
    # onto the same socket (and garbling the underlying SSL session).
    # We ensure each process gets its own set of connections here by
    # closing all connections in the storage provider connection pool.
    connection_pool = StorageUri.provider_pool
    if connection_pool:
      for i in connection_pool:
        connection_pool[i].connection.close()

  def _GetProcessAndThreadCount(self, process_count, thread_count,
                                parallel_operations_override):
    """Determines the values of process_count and thread_count.

    These values are used for parallel operations.
    If we're not performing operations in parallel, then ignore
    existing values and use process_count = thread_count = 1.

    Args:
      process_count: A positive integer or None. In the latter case, we read
                     the value from the .boto config file.
      thread_count: A positive integer or None. In the latter case, we read
                    the value from the .boto config file.
      parallel_operations_override: Used to override self.parallel_operations.
                                    This allows the caller to safely override
                                    the top-level flag for a single call.

    Returns:
      (process_count, thread_count): The number of processes and threads to use,
                                     respectively.
    """
    # Set OS process and python thread count as a function of options
    # and config.
    if self.parallel_operations or parallel_operations_override:
      if not process_count:
        process_count = boto.config.getint(
            'GSUtil', 'parallel_process_count',
            gslib.commands.config.DEFAULT_PARALLEL_PROCESS_COUNT)
      if process_count < 1:
        raise CommandException('Invalid parallel_process_count "%d".' %
                               process_count)
      if not thread_count:
        thread_count = boto.config.getint(
            'GSUtil', 'parallel_thread_count',
            gslib.commands.config.DEFAULT_PARALLEL_THREAD_COUNT)
      if thread_count < 1:
        raise CommandException('Invalid parallel_thread_count "%d".' %
                               thread_count)
    else:
      # If -m not specified, then assume 1 OS process and 1 Python thread.
      process_count = 1
      thread_count = 1

    if IS_WINDOWS and process_count > 1:
      raise CommandException('\n'.join(textwrap.wrap(
          ('It is not possible to set process_count > 1 on Windows. Please '
           'update your config file (located at %s) and set '
           '"parallel_process_count = 1".') %
          GetConfigFilePath())))
    self.logger.debug('process count: %d', process_count)
    self.logger.debug('thread count: %d', thread_count)

    return (process_count, thread_count)

  def _SetUpPerCallerState(self):
    """Set up the state for a caller id, corresponding to one Apply call."""
    # pylint: disable=global-variable-undefined,global-variable-not-assigned
    # These variables are initialized in InitializeMultiprocessingVariables or
    # InitializeThreadingVariables
    global global_return_values_map, shared_vars_map, failure_count
    global caller_id_finished_count, shared_vars_list_map, total_tasks
    global need_pool_or_done_cond, call_completed_map, class_map
    global task_queues, caller_id_lock, caller_id_counter
    # Get a new caller ID.
    with caller_id_lock:
      if isinstance(caller_id_counter, int):
        caller_id_counter += 1
        caller_id = caller_id_counter
      else:
        caller_id_counter.value += 1
        caller_id = caller_id_counter.value

    # Create a copy of self with an incremented recursive level. This allows
    # the class to report its level correctly if the function called from it
    # also needs to call Apply.
    cls = copy.copy(self)
    cls.recursive_apply_level += 1

    # Thread-safe loggers can't be pickled, so we will remove it here and
    # recreate it later in the WorkerThread. This is not a problem since any
    # logger with the same name will be treated as a singleton.
    cls.logger = None

    # Likewise, the default API connection can't be pickled, but it is unused
    # anyway as each thread gets its own API delegator.
    cls.gsutil_api = None

    class_map[caller_id] = cls
    total_tasks[caller_id] = -1  # -1 => the producer hasn't finished yet.
    call_completed_map[caller_id] = False
    caller_id_finished_count[caller_id] = 0
    global_return_values_map[caller_id] = []
    return caller_id

  def _CreateNewConsumerPool(self, num_processes, num_threads):
    """Create a new pool of processes that call _ApplyThreads."""
    processes = []
    task_queue = _NewMultiprocessingQueue()
    task_queues.append(task_queue)

    current_max_recursive_level.value += 1
    if current_max_recursive_level.value > MAX_RECURSIVE_DEPTH:
      raise CommandException('Recursion depth of Apply calls is too great.')
    for _ in range(num_processes):
      recursive_apply_level = len(consumer_pools)
      p = multiprocessing.Process(
          target=self._ApplyThreads,
          args=(num_threads, num_processes, recursive_apply_level))
      p.daemon = True
      processes.append(p)
      p.start()
    consumer_pool = _ConsumerPool(processes, task_queue)
    consumer_pools.append(consumer_pool)

  def Apply(self, func, args_iterator, exception_handler,
            shared_attrs=None, arg_checker=_UrlArgChecker,
            parallel_operations_override=False, process_count=None,
            thread_count=None, should_return_results=False,
            fail_on_error=False):
    """Calls _Parallel/SequentialApply based on multiprocessing availability.

    Args:
      func: Function to call to process each argument.
      args_iterator: Iterable collection of arguments to be put into the
                     work queue.
      exception_handler: Exception handler for WorkerThread class.
      shared_attrs: List of attributes to manage across sub-processes.
      arg_checker: Used to determine whether we should process the current
                   argument or simply skip it. Also handles any logging that
                   is specific to a particular type of argument.
      parallel_operations_override: Used to override self.parallel_operations.
                                    This allows the caller to safely override
                                    the top-level flag for a single call.
      process_count: The number of processes to use. If not specified, then
                     the configured default will be used.
      thread_count: The number of threads per process. If not speficied, then
                    the configured default will be used..
      should_return_results: If true, then return the results of all successful
                             calls to func in a list.
      fail_on_error: If true, then raise any exceptions encountered when
                     executing func. This is only applicable in the case of
                     process_count == thread_count == 1.

    Returns:
      Results from spawned threads.
    """
    if shared_attrs:
      original_shared_vars_values = {}  # We'll add these back in at the end.
      for name in shared_attrs:
        original_shared_vars_values[name] = getattr(self, name)
        # By setting this to 0, we simplify the logic for computing deltas.
        # We'll add it back after all of the tasks have been performed.
        setattr(self, name, 0)

    (process_count, thread_count) = self._GetProcessAndThreadCount(
        process_count, thread_count, parallel_operations_override)

    is_main_thread = (self.recursive_apply_level == 0
                      and self.sequential_caller_id == -1)

    # We don't honor the fail_on_error flag in the case of multiple threads
    # or processes.
    fail_on_error = fail_on_error and (process_count * thread_count == 1)

    # Only check this from the first call in the main thread. Apart from the
    # fact that it's  wasteful to try this multiple times in general, it also
    # will never work when called from a subprocess since we use daemon
    # processes, and daemons can't create other processes.
    if (is_main_thread and not self.multiprocessing_is_available and
        process_count > 1):
      # Run the check again and log the appropriate warnings. This was run
      # before, when the Command object was created, in order to calculate
      # self.multiprocessing_is_available, but we don't want to print the
      # warning until we're sure the user actually tried to use multiple
      # threads or processes.
      CheckMultiprocessingAvailableAndInit(logger=self.logger)

    caller_id = self._SetUpPerCallerState()

    # If any shared attributes passed by caller, create a dictionary of
    # shared memory variables for every element in the list of shared
    # attributes.
    if shared_attrs:
      shared_vars_list_map[caller_id] = shared_attrs
      for name in shared_attrs:
        shared_vars_map[(caller_id, name)] = 0

    # Make all of the requested function calls.
    usable_processes_count = (process_count if self.multiprocessing_is_available
                              else 1)
    if thread_count * usable_processes_count > 1:
      self._ParallelApply(func, args_iterator, exception_handler, caller_id,
                          arg_checker, usable_processes_count, thread_count,
                          should_return_results, fail_on_error)
    else:
      self._SequentialApply(func, args_iterator, exception_handler, caller_id,
                            arg_checker, should_return_results, fail_on_error)

    if shared_attrs:
      for name in shared_attrs:
        # This allows us to retain the original value of the shared variable,
        # and simply apply the delta after what was done during the call to
        # apply.
        final_value = (original_shared_vars_values[name] +
                       shared_vars_map.get((caller_id, name)))
        setattr(self, name, final_value)

    if should_return_results:
      return global_return_values_map.get(caller_id)

  def _MaybeSuggestGsutilDashM(self):
    """Outputs a sugestion to the user to use gsutil -m."""
    if not (boto.config.getint('GSUtil', 'parallel_process_count', 0) == 1 and
            boto.config.getint('GSUtil', 'parallel_thread_count', 0) == 1):
      self.logger.info('\n' + textwrap.fill(
          '==> NOTE: You are performing a sequence of gsutil operations that '
          'may run significantly faster if you instead use gsutil -m %s ...\n'
          'Please see the -m section under "gsutil help options" for further '
          'information about when gsutil -m can be advantageous.'
          % sys.argv[1]) + '\n')

  # pylint: disable=g-doc-args
  def _SequentialApply(self, func, args_iterator, exception_handler, caller_id,
                       arg_checker, should_return_results, fail_on_error):
    """Performs all function calls sequentially in the current thread.

    No other threads or processes will be spawned. This degraded functionality
    is used when the multiprocessing module is not available or the user
    requests only one thread and one process.
    """
    # Create a WorkerThread to handle all of the logic needed to actually call
    # the function. Note that this thread will never be started, and all work
    # is done in the current thread.
    worker_thread = WorkerThread(None, False)
    args_iterator = iter(args_iterator)
    # Count of sequential calls that have been made. Used for producing
    # suggestion to use gsutil -m.
    sequential_call_count = 0
    while True:

      # Try to get the next argument, handling any exceptions that arise.
      try:
        args = args_iterator.next()
      except StopIteration, e:
        break
      except Exception, e:  # pylint: disable=broad-except
        _IncrementFailureCount()
        if fail_on_error:
          raise
        else:
          try:
            exception_handler(self, e)
          except Exception, _:  # pylint: disable=broad-except
            self.logger.debug(
                'Caught exception while handling exception for %s:\n%s',
                func, traceback.format_exc())
          continue

      sequential_call_count += 1
      if sequential_call_count == OFFER_GSUTIL_M_SUGGESTION_THRESHOLD:
        # Output suggestion near beginning of run, so user sees it early and can
        # ^C and try gsutil -m.
        self._MaybeSuggestGsutilDashM()
      if arg_checker(self, args):
        # Now that we actually have the next argument, perform the task.
        task = Task(func, args, caller_id, exception_handler,
                    should_return_results, arg_checker, fail_on_error)
        worker_thread.PerformTask(task, self)
    if sequential_call_count >= gslib.util.GetTermLines():
      # Output suggestion at end of long run, in case user missed it at the
      # start and it scrolled off-screen.
      self._MaybeSuggestGsutilDashM()

    # If the final iterated argument results in an exception, and that
    # exception modifies shared_attrs, we need to publish the results.
    worker_thread.shared_vars_updater.Update(caller_id, self)

  # pylint: disable=g-doc-args
  def _ParallelApply(self, func, args_iterator, exception_handler, caller_id,
                     arg_checker, process_count, thread_count,
                     should_return_results, fail_on_error):
    """Dispatches input arguments across a thread/process pool.

    Pools are composed of parallel OS processes and/or Python threads,
    based on options (-m or not) and settings in the user's config file.

    If only one OS process is requested/available, dispatch requests across
    threads in the current OS process.

    In the multi-process case, we will create one pool of worker processes for
    each level of the tree of recursive calls to Apply. E.g., if A calls
    Apply(B), and B ultimately calls Apply(C) followed by Apply(D), then we
    will only create two sets of worker processes - B will execute in the first,
    and C and D will execute in the second. If C is then changed to call
    Apply(E) and D is changed to call Apply(F), then we will automatically
    create a third set of processes (lazily, when needed) that will be used to
    execute calls to E and F. This might look something like:

    Pool1 Executes:                B
                                  / \
    Pool2 Executes:              C   D
                                /     \
    Pool3 Executes:            E       F

    Apply's parallelism is generally broken up into 4 cases:
    - If process_count == thread_count == 1, then all tasks will be executed
      by _SequentialApply.
    - If process_count > 1 and thread_count == 1, then the main thread will
      create a new pool of processes (if they don't already exist) and each of
      those processes will execute the tasks in a single thread.
    - If process_count == 1 and thread_count > 1, then this process will create
      a new pool of threads to execute the tasks.
    - If process_count > 1 and thread_count > 1, then the main thread will
      create a new pool of processes (if they don't already exist) and each of
      those processes will, upon creation, create a pool of threads to
      execute the tasks.

    Args:
      caller_id: The caller ID unique to this call to command.Apply.
      See command.Apply for description of other arguments.
    """
    is_main_thread = self.recursive_apply_level == 0

    # Catch SIGINT and SIGTERM under Linux/MacOs so we can do cleanup before
    # exiting.
    if not IS_WINDOWS and is_main_thread:
      # Register as a final signal handler because this handler kills the
      # main gsutil process (so it must run last).
      RegisterSignalHandler(signal.SIGINT, self._HandleMultiProcessingSigs,
                            is_final_handler=True)
      RegisterSignalHandler(signal.SIGTERM, self._HandleMultiProcessingSigs,
                            is_final_handler=True)

    if not task_queues:
      # The process we create will need to access the next recursive level
      # of task queues if it makes a call to Apply, so we always keep around
      # one more queue than we know we need. OTOH, if we don't create a new
      # process, the existing process still needs a task queue to use.
      if process_count > 1:
        task_queues.append(_NewMultiprocessingQueue())
      else:
        task_queues.append(_NewThreadsafeQueue())

    if process_count > 1:  # Handle process pool creation.
      # Check whether this call will need a new set of workers.

      # Each worker must acquire a shared lock before notifying the main thread
      # that it needs a new worker pool, so that at most one worker asks for
      # a new worker pool at once.
      try:
        if not is_main_thread:
          worker_checking_level_lock.acquire()
        if self.recursive_apply_level >= current_max_recursive_level.value:
          with need_pool_or_done_cond:
            # Only the main thread is allowed to create new processes -
            # otherwise, we will run into some Python bugs.
            if is_main_thread:
              self._CreateNewConsumerPool(process_count, thread_count)
            else:
              # Notify the main thread that we need a new consumer pool.
              new_pool_needed.value = 1
              need_pool_or_done_cond.notify_all()
              # The main thread will notify us when it finishes.
              need_pool_or_done_cond.wait()
      finally:
        if not is_main_thread:
          worker_checking_level_lock.release()

    # If we're running in this process, create a separate task queue. Otherwise,
    # if Apply has already been called with process_count > 1, then there will
    # be consumer pools trying to use our processes.
    if process_count > 1:
      task_queue = task_queues[self.recursive_apply_level]
    elif self.multiprocessing_is_available:
      task_queue = _NewMultiprocessingQueue()
    else:
      task_queue = _NewThreadsafeQueue()

    # Kick off a producer thread to throw tasks in the global task queue. We
    # do this asynchronously so that the main thread can be free to create new
    # consumer pools when needed (otherwise, any thread with a task that needs
    # a new consumer pool must block until we're completely done producing; in
    # the worst case, every worker blocks on such a call and the producer fills
    # up the task queue before it finishes, so we block forever).
    producer_thread = ProducerThread(copy.copy(self), args_iterator, caller_id,
                                     func, task_queue, should_return_results,
                                     exception_handler, arg_checker,
                                     fail_on_error)

    if process_count > 1:
      # Wait here until either:
      #   1. We're the main thread and someone needs a new consumer pool - in
      #      which case we create one and continue waiting.
      #   2. Someone notifies us that all of the work we requested is done, in
      #      which case we retrieve the results (if applicable) and stop
      #      waiting.
      while True:
        with need_pool_or_done_cond:
          # Either our call is done, or someone needs a new level of consumer
          # pools, or we the wakeup call was meant for someone else. It's
          # impossible for both conditions to be true, since the main thread is
          # blocked on any other ongoing calls to Apply, and a thread would not
          # ask for a new consumer pool unless it had more work to do.
          if call_completed_map[caller_id]:
            break
          elif is_main_thread and new_pool_needed.value:
            new_pool_needed.value = 0
            self._CreateNewConsumerPool(process_count, thread_count)
            need_pool_or_done_cond.notify_all()

          # Note that we must check the above conditions before the wait() call;
          # otherwise, the notification can happen before we start waiting, in
          # which case we'll block forever.
          need_pool_or_done_cond.wait()
    else:  # Using a single process.
      self._ApplyThreads(thread_count, process_count,
                         self.recursive_apply_level,
                         is_blocking_call=True, task_queue=task_queue)

    # We encountered an exception from the producer thread before any arguments
    # were enqueued, but it wouldn't have been propagated, so we'll now
    # explicitly raise it here.
    if producer_thread.unknown_exception:
      # pylint: disable=raising-bad-type
      raise producer_thread.unknown_exception

    # We encountered an exception from the producer thread while iterating over
    # the arguments, so raise it here if we're meant to fail on error.
    if producer_thread.iterator_exception and fail_on_error:
      # pylint: disable=raising-bad-type
      raise producer_thread.iterator_exception

  def _ApplyThreads(self, thread_count, process_count, recursive_apply_level,
                    is_blocking_call=False, task_queue=None):
    """Assigns the work from the multi-process global task queue.

    Work is assigned to an individual process for later consumption either by
    the WorkerThreads or (if thread_count == 1) this thread.

    Args:
      thread_count: The number of threads used to perform the work. If 1, then
                    perform all work in this thread.
      process_count: The number of processes used to perform the work.
      recursive_apply_level: The depth in the tree of recursive calls to Apply
                             of this thread.
      is_blocking_call: True iff the call to Apply is blocked on this call
                        (which is true iff process_count == 1), implying that
                        _ApplyThreads must behave as a blocking call.
    """
    self._ResetConnectionPool()
    self.recursive_apply_level = recursive_apply_level

    task_queue = task_queue or task_queues[recursive_apply_level]

    # Ensure fairness across processes by filling our WorkerPool only with
    # as many tasks as it has WorkerThreads. This semaphore is acquired each
    # time that a task is retrieved from the queue and released each time
    # a task is completed by a WorkerThread.
    worker_semaphore = threading.BoundedSemaphore(thread_count)

    assert thread_count * process_count > 1, (
        'Invalid state, calling command._ApplyThreads with only one thread '
        'and process.')
    # TODO: Presently, this pool gets recreated with each call to Apply. We
    # should be able to do it just once, at process creation time.
    worker_pool = WorkerPool(
        thread_count, self.logger, worker_semaphore,
        bucket_storage_uri_class=self.bucket_storage_uri_class,
        gsutil_api_map=self.gsutil_api_map, debug=self.debug)

    num_enqueued = 0
    while True:
      worker_semaphore.acquire()
      task = task_queue.get()
      if task.args != ZERO_TASKS_TO_DO_ARGUMENT:
        # If we have no tasks to do and we're performing a blocking call, we
        # need a special signal to tell us to stop - otherwise, we block on
        # the call to task_queue.get() forever.
        worker_pool.AddTask(task)
        num_enqueued += 1
      else:
        # No tasks remain; don't block the semaphore on WorkerThread completion.
        worker_semaphore.release()

      if is_blocking_call:
        num_to_do = total_tasks[task.caller_id]
        # The producer thread won't enqueue the last task until after it has
        # updated total_tasks[caller_id], so we know that num_to_do < 0 implies
        # we will do this check again.
        if num_to_do >= 0 and num_enqueued == num_to_do:
          if thread_count == 1:
            return
          else:
            while True:
              with need_pool_or_done_cond:
                if call_completed_map[task.caller_id]:
                  # We need to check this first, in case the condition was
                  # notified before we grabbed the lock.
                  return
                need_pool_or_done_cond.wait()


# Below here lie classes and functions related to controlling the flow of tasks
# between various threads and processes.


class _ConsumerPool(object):

  def __init__(self, processes, task_queue):
    self.processes = processes
    self.task_queue = task_queue

  def ShutDown(self):
    for process in self.processes:
      KillProcess(process.pid)


def KillProcess(pid):
  """Make best effort to kill the given process.

  We ignore all exceptions so a caller looping through a list of processes will
  continue attempting to kill each, even if one encounters a problem.

  Args:
    pid: The process ID.
  """
  try:
    # os.kill doesn't work in 2.X or 3.Y on Windows for any X < 7 or Y < 2.
    if IS_WINDOWS and ((2, 6) <= sys.version_info[:3] < (2, 7) or
                       (3, 0) <= sys.version_info[:3] < (3, 2)):
      kernel32 = ctypes.windll.kernel32
      handle = kernel32.OpenProcess(1, 0, pid)
      kernel32.TerminateProcess(handle, 0)
    else:
      os.kill(pid, signal.SIGKILL)
  except:  # pylint: disable=bare-except
    pass


class Task(namedtuple('Task', (
    'func args caller_id exception_handler should_return_results arg_checker '
    'fail_on_error'))):
  """Task class representing work to be completed.

  Args:
    func: The function to be executed.
    args: The arguments to func.
    caller_id: The globally-unique caller ID corresponding to the Apply call.
    exception_handler: The exception handler to use if the call to func fails.
    should_return_results: True iff the results of this function should be
                           returned from the Apply call.
    arg_checker: Used to determine whether we should process the current
                 argument or simply skip it. Also handles any logging that
                 is specific to a particular type of argument.
    fail_on_error: If true, then raise any exceptions encountered when
                   executing func. This is only applicable in the case of
                   process_count == thread_count == 1.
  """
  pass


class ProducerThread(threading.Thread):
  """Thread used to enqueue work for other processes and threads."""

  def __init__(self, cls, args_iterator, caller_id, func, task_queue,
               should_return_results, exception_handler, arg_checker,
               fail_on_error):
    """Initializes the producer thread.

    Args:
      cls: Instance of Command for which this ProducerThread was created.
      args_iterator: Iterable collection of arguments to be put into the
                     work queue.
      caller_id: Globally-unique caller ID corresponding to this call to Apply.
      func: The function to be called on each element of args_iterator.
      task_queue: The queue into which tasks will be put, to later be consumed
                  by Command._ApplyThreads.
      should_return_results: True iff the results for this call to command.Apply
                             were requested.
      exception_handler: The exception handler to use when errors are
                         encountered during calls to func.
      arg_checker: Used to determine whether we should process the current
                   argument or simply skip it. Also handles any logging that
                   is specific to a particular type of argument.
      fail_on_error: If true, then raise any exceptions encountered when
                     executing func. This is only applicable in the case of
                     process_count == thread_count == 1.
    """
    super(ProducerThread, self).__init__()
    self.func = func
    self.cls = cls
    self.args_iterator = args_iterator
    self.caller_id = caller_id
    self.task_queue = task_queue
    self.arg_checker = arg_checker
    self.exception_handler = exception_handler
    self.should_return_results = should_return_results
    self.fail_on_error = fail_on_error
    self.shared_variables_updater = _SharedVariablesUpdater()
    self.daemon = True
    self.unknown_exception = None
    self.iterator_exception = None
    self.start()

  def run(self):
    num_tasks = 0
    cur_task = None
    last_task = None
    try:
      args_iterator = iter(self.args_iterator)
      while True:
        try:
          args = args_iterator.next()
        except StopIteration, e:
          break
        except Exception, e:  # pylint: disable=broad-except
          _IncrementFailureCount()
          if self.fail_on_error:
            self.iterator_exception = e
            raise
          else:
            try:
              self.exception_handler(self.cls, e)
            except Exception, _:  # pylint: disable=broad-except
              self.cls.logger.debug(
                  'Caught exception while handling exception for %s:\n%s',
                  self.func, traceback.format_exc())
            self.shared_variables_updater.Update(self.caller_id, self.cls)
            continue

        if self.arg_checker(self.cls, args):
          num_tasks += 1
          last_task = cur_task
          cur_task = Task(self.func, args, self.caller_id,
                          self.exception_handler, self.should_return_results,
                          self.arg_checker, self.fail_on_error)
          if last_task:
            self.task_queue.put(last_task)
    except Exception, e:  # pylint: disable=broad-except
      # This will also catch any exception raised due to an error in the
      # iterator when fail_on_error is set, so check that we failed for some
      # other reason before claiming that we had an unknown exception.
      if not self.iterator_exception:
        self.unknown_exception = e
    finally:
      # We need to make sure to update total_tasks[caller_id] before we enqueue
      # the last task. Otherwise, a worker can retrieve the last task and
      # complete it, then check total_tasks and determine that we're not done
      # producing all before we update total_tasks. This approach forces workers
      # to wait on the last task until after we've updated total_tasks.
      total_tasks[self.caller_id] = num_tasks
      if not cur_task:
        # This happens if there were zero arguments to be put in the queue.
        cur_task = Task(None, ZERO_TASKS_TO_DO_ARGUMENT, self.caller_id,
                        None, None, None, None)
      self.task_queue.put(cur_task)

      # It's possible that the workers finished before we updated total_tasks,
      # so we need to check here as well.
      _NotifyIfDone(self.caller_id,
                    caller_id_finished_count.get(self.caller_id))


class WorkerPool(object):
  """Pool of worker threads to which tasks can be added."""

  def __init__(self, thread_count, logger, worker_semaphore,
               bucket_storage_uri_class=None, gsutil_api_map=None, debug=0):
    self.task_queue = _NewThreadsafeQueue()
    self.threads = []
    for _ in range(thread_count):
      worker_thread = WorkerThread(
          self.task_queue, logger, worker_semaphore=worker_semaphore,
          bucket_storage_uri_class=bucket_storage_uri_class,
          gsutil_api_map=gsutil_api_map, debug=debug)
      self.threads.append(worker_thread)
      worker_thread.start()

  def AddTask(self, task):
    self.task_queue.put(task)


class WorkerThread(threading.Thread):
  """Thread where all the work will be performed.

  This makes the function calls for Apply and takes care of all error handling,
  return value propagation, and shared_vars.

  Note that this thread is NOT started upon instantiation because the function-
  calling logic is also used in the single-threaded case.
  """

  def __init__(self, task_queue, logger, worker_semaphore=None,
               bucket_storage_uri_class=None, gsutil_api_map=None, debug=0):
    """Initializes the worker thread.

    Args:
      task_queue: The thread-safe queue from which this thread should obtain
                  its work.
      logger: Logger to use for this thread.
      worker_semaphore: threading.BoundedSemaphore to be released each time a
          task is completed, or None for single-threaded execution.
      bucket_storage_uri_class: Class to instantiate for cloud StorageUris.
                                Settable for testing/mocking.
      gsutil_api_map: Map of providers and API selector tuples to api classes
                      which can be used to communicate with those providers.
                      Used for the instantiating CloudApiDelegator class.
      debug: debug level for the CloudApiDelegator class.
    """
    super(WorkerThread, self).__init__()
    self.task_queue = task_queue
    self.worker_semaphore = worker_semaphore
    self.daemon = True
    self.cached_classes = {}
    self.shared_vars_updater = _SharedVariablesUpdater()

    self.thread_gsutil_api = None
    if bucket_storage_uri_class and gsutil_api_map:
      self.thread_gsutil_api = CloudApiDelegator(
          bucket_storage_uri_class, gsutil_api_map, logger, debug=debug)

  def PerformTask(self, task, cls):
    """Makes the function call for a task.

    Args:
      task: The Task to perform.
      cls: The instance of a class which gives context to the functions called
           by the Task's function. E.g., see SetAclFuncWrapper.
    """
    caller_id = task.caller_id
    try:
      results = task.func(cls, task.args, thread_state=self.thread_gsutil_api)
      if task.should_return_results:
        global_return_values_map.Increment(caller_id, [results],
                                           default_value=[])
    except Exception, e:  # pylint: disable=broad-except
      _IncrementFailureCount()
      if task.fail_on_error:
        raise  # Only happens for single thread and process case.
      else:
        try:
          task.exception_handler(cls, e)
        except Exception, _:  # pylint: disable=broad-except
          # Don't allow callers to raise exceptions here and kill the worker
          # threads.
          cls.logger.debug(
              'Caught exception while handling exception for %s:\n%s',
              task, traceback.format_exc())
    finally:
      if self.worker_semaphore:
        self.worker_semaphore.release()
      self.shared_vars_updater.Update(caller_id, cls)

      # Even if we encounter an exception, we still need to claim that that
      # the function finished executing. Otherwise, we won't know when to
      # stop waiting and return results.
      num_done = caller_id_finished_count.Increment(caller_id, 1)
      _NotifyIfDone(caller_id, num_done)

  def run(self):
    while True:
      task = self.task_queue.get()
      caller_id = task.caller_id

      # Get the instance of the command with the appropriate context.
      cls = self.cached_classes.get(caller_id, None)
      if not cls:
        cls = copy.copy(class_map[caller_id])
        cls.logger = CreateGsutilLogger(cls.command_name)
        self.cached_classes[caller_id] = cls

      self.PerformTask(task, cls)


class _SharedVariablesUpdater(object):
  """Used to update shared variable for a class in the global map.

     Note that each thread will have its own instance of the calling class for
     context, and it will also have its own instance of a
     _SharedVariablesUpdater.  This is used in the following way:

     1. Before any tasks are performed, each thread will get a copy of the
        calling class, and the globally-consistent value of this shared variable
        will be initialized to whatever it was before the call to Apply began.

     2. After each time a thread performs a task, it will look at the current
        values of the shared variables in its instance of the calling class.

        2.A. For each such variable, it computes the delta of this variable
             between the last known value for this class (which is stored in
             a dict local to this class) and the current value of the variable
             in the class.

        2.B. Using this delta, we update the last known value locally as well
             as the globally-consistent value shared across all classes (the
             globally consistent value is simply increased by the computed
             delta).
  """

  def __init__(self):
    self.last_shared_var_values = {}

  def Update(self, caller_id, cls):
    """Update any shared variables with their deltas."""
    shared_vars = shared_vars_list_map.get(caller_id, None)
    if shared_vars:
      for name in shared_vars:
        key = (caller_id, name)
        last_value = self.last_shared_var_values.get(key, 0)
        # Compute the change made since the last time we updated here. This is
        # calculated by simply subtracting the last known value from the current
        # value in the class instance.
        delta = getattr(cls, name) - last_value
        self.last_shared_var_values[key] = delta + last_value

        # Update the globally-consistent value by simply increasing it by the
        # computed delta.
        shared_vars_map.Increment(key, delta)


def _NotifyIfDone(caller_id, num_done):
  """Notify any threads waiting for results that something has finished.

  Each waiting thread will then need to check the call_completed_map to see if
  its work is done.

  Note that num_done could be calculated here, but it is passed in as an
  optimization so that we have one less call to a globally-locked data
  structure.

  Args:
    caller_id: The caller_id of the function whose progress we're checking.
    num_done: The number of tasks currently completed for that caller_id.
  """
  num_to_do = total_tasks[caller_id]
  if num_to_do == num_done and num_to_do >= 0:
    # Notify the Apply call that's sleeping that it's ready to return.
    with need_pool_or_done_cond:
      call_completed_map[caller_id] = True
      need_pool_or_done_cond.notify_all()


def ShutDownGsutil():
  """Shut down all processes in consumer pools in preparation for exiting."""
  for q in queues:
    try:
      q.cancel_join_thread()
    except:  # pylint: disable=bare-except
      pass
  for consumer_pool in consumer_pools:
    consumer_pool.ShutDown()


# pylint: disable=global-variable-undefined
def _IncrementFailureCount():
  global failure_count
  if isinstance(failure_count, int):
    failure_count += 1
  else:  # Otherwise it's a multiprocessing.Value() of type 'i'.
    failure_count.value += 1


# pylint: disable=global-variable-undefined
def GetFailureCount():
  """Returns the number of failures processed during calls to Apply()."""
  try:
    if isinstance(failure_count, int):
      return failure_count
    else:  # It's a multiprocessing.Value() of type 'i'.
      return failure_count.value
  except NameError:  # If it wasn't initialized, Apply() wasn't called.
    return 0


def ResetFailureCount():
  """Resets the failure_count variable to 0 - useful if error is expected."""
  try:
    global failure_count
    if isinstance(failure_count, int):
      failure_count = 0
    else:  # It's a multiprocessing.Value() of type 'i'.
      failure_count = multiprocessing.Value('i', 0)
  except NameError:  # If it wasn't initialized, Apply() wasn't called.
    pass
