# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A common base class for pages that are used to edit configs."""

from google.appengine.api import taskqueue

from dashboard import list_tests
from dashboard import request_handler
from dashboard import utils
from dashboard import xsrf

# Max number of entities to put in one request to /put_entities_task.
_MAX_TESTS_TO_PUT_AT_ONCE = 25

# The queue to use to re-put tests. Should be present in queue.yaml.
_TASK_QUEUE_NAME = 'edit-sheriffs-queue'

# Minimum time before starting tasks, in seconds. It appears that the tasks
# may be executed before the sheriff is saved, so this is a workaround for that.
# See http://crbug.com/621499
_TASK_QUEUE_COUNTDOWN = 60


class EditConfigHandler(request_handler.RequestHandler):
  """Base class for handlers that are used to add or edit entities.

  Specifically, this is a common base class for EditSheriffsHandler
  and EditAnomalyConfigsHandler. Both of these kinds of entities
  represent a configuration that can apply to a set of tests, where
  the set of tests is specified with a list of test path patterns.
  """

  # The webapp2 docs say that custom __init__ methods should call initialize()
  # at the beginning of the method (rather than calling super __init__). See:
  # https://webapp-improved.appspot.com/guide/handlers.html#overriding-init
  # pylint: disable=super-init-not-called
  def __init__(self, request, response, model_class):
    """Constructs a handler object for editing entities of the given class.

    Args:
      request: Request object (implicitly passed in by webapp2).
      response: Response object (implicitly passed in by webapp2).
      model_class: A subclass of ndb.Model.
    """
    self.initialize(request, response)
    self._model_class = model_class

  @xsrf.TokenRequired
  def post(self):
    """Updates the user-selected anomaly threshold configuration.

    Request parameters:
      add-edit: Either 'add' if adding a new config, or 'edit'.
      add-name: A new anomaly config name, if adding one.
      edit-name: An existing anomaly config name, if editing one.
      patterns: Newline-separated list of test path patterns to monitor.

    Depending on the specific sub-class, this will also take other
    parameters for specific properties of the entity being edited.
    """
    try:
      edit_type = self.request.get('add-edit')
      if edit_type == 'add':
        self._AddEntity()
      elif edit_type == 'edit':
        self._EditEntity()
      else:
        raise request_handler.InvalidInputError('Invalid value for add-edit.')
    except request_handler.InvalidInputError as error:
      message = str(error) + ' Model class: ' + self._model_class.__name__
      self.RenderHtml('result.html', {'errors': [message]})

  def _AddEntity(self):
    """Adds adds a new entity according to the request parameters."""
    name = self.request.get('add-name')
    if not name:
      raise request_handler.InvalidInputError('No name given when adding new ')
    if self._model_class.get_by_id(name):
      raise request_handler.InvalidInputError(
          'Entity "%s" already exists, cannot add.' % name)
    entity = self._model_class(id=name)
    self._UpdateAndReportResults(entity)

  def _EditEntity(self):
    """Edits an existing entity according to the request parameters."""
    name = self.request.get('edit-name')
    if not name:
      raise request_handler.InvalidInputError('No name given.')
    entity = self._model_class.get_by_id(name)
    if not entity:
      raise request_handler.InvalidInputError(
          'Entity "%s" does not exist, cannot edit.' % name)
    self._UpdateAndReportResults(entity)

  def _UpdateAndReportResults(self, entity):
    """Updates the entity and reports the results of this updating."""
    new_patterns = _SplitPatternLines(self.request.get('patterns'))
    old_patterns = entity.patterns
    entity.patterns = new_patterns
    self._UpdateFromRequestParameters(entity)
    entity.put()
    added_test_paths, removed_test_paths = _ChangeTestPatterns(
        old_patterns, new_patterns)
    self._RenderResults(entity, added_test_paths, removed_test_paths)

  def _UpdateFromRequestParameters(self, entity):
    """Updates the given entity based on query parameters.

    This method does not need to put() the entity.

    Args:
      entity: The entity to update.
    """
    raise NotImplementedError()

  def _RenderResults(self, entity, added_test_paths, removed_test_paths):
    """Outputs results using the results.html template.

    Args:
      entity: The entity that was edited.
      added_test_paths: New tests that this config now applies to.
      removed_test_paths: Tests that this config no longer applies to.
    """
    def ResultEntry(name, value):
      """Returns an entry in the results lists to embed on result.html."""
      return {'name': name, 'value': value, 'class': 'results-pre'}

    self.RenderHtml('result.html', {
        'headline': ('Added or updated %s "%s".' %
                     (self._model_class.__name__, entity.key.string_id())),
        'results': [
            ResultEntry('Entity', str(entity)),
            ResultEntry('Added tests', '\n'.join(added_test_paths)),
            ResultEntry('Removed tests', '\n'.join(removed_test_paths)),
        ]
    })


def _SplitPatternLines(patterns_string):
  """Splits up the given newline-separated patterns and validates them."""
  test_path_patterns = sorted(p for p in patterns_string.splitlines() if p)
  _ValidatePatterns(test_path_patterns)
  return test_path_patterns


def _ValidatePatterns(test_path_patterns):
  """Raises an exception if any test path patterns are invalid."""
  for pattern in test_path_patterns:
    if not _IsValidTestPathPattern(pattern):
      raise request_handler.InvalidInputError(
          'Invalid test path pattern: "%s"' % pattern)


def _IsValidTestPathPattern(test_path_pattern):
  """Checks whether the given test path pattern string is OK."""
  if '[' in test_path_pattern or ']' in test_path_pattern:
    return False
  # Valid test paths will have a Master, bot, and test suite, and will
  # generally have a chart name and trace name after that.
  return len(test_path_pattern.split('/')) >= 3


def _ChangeTestPatterns(old_patterns, new_patterns):
  """Updates tests that are different between old_patterns and new_patterns.

  The two arguments both represent sets of test paths (i.e. sets of data
  series). Any tests that are different between these two sets need to be
  updated.

  Some properties of TestMetadata entities are updated when they are put in the
  |_pre_put_hook| method of TestMetadata, so any TestMetadata entity that might
  need to be updated should be re-put.

  Args:
    old_patterns: An iterable of test path pattern strings.
    new_patterns: Another iterable of test path pattern strings.

  Returns:
    A pair (added_test_paths, removed_test_paths), which are, respectively,
    the test paths that are in the new set but not the old, and those that
    are in the old set but not the new.
  """
  added_patterns, removed_patterns = _ComputeDeltas(old_patterns, new_patterns)
  added_test_paths = _AllTestPathsMatchingPatterns(added_patterns)
  removed_test_paths = _AllTestPathsMatchingPatterns(removed_patterns)
  _AddTestsToPutToTaskQueue(added_test_paths + removed_test_paths)
  return _RemoveOverlapping(added_test_paths, removed_test_paths)


def _ComputeDeltas(old_items, new_items):
  """Finds the added and removed items in a new set compared to an old one.

  Args:
    old_items: A collection of existing items. Could be a list or set.
    new_items: Another collection of items.

  Returns:
    A pair of sets (added, removed).
  """
  old, new = set(old_items), set(new_items)
  return new - old, old - new


def _RemoveOverlapping(added_items, removed_items):
  """Returns two sets of items with the common items removed."""
  added, removed = set(added_items), set(removed_items)
  return added - removed, removed - added


def _AllTestPathsMatchingPatterns(patterns_list):
  """Returns a list of all test paths matching the given list of patterns."""
  test_paths = set()
  for pattern in patterns_list:
    test_paths |= set(list_tests.GetTestsMatchingPattern(pattern))
  return sorted(test_paths)


def _AddTestsToPutToTaskQueue(test_paths):
  """Adds tests that we want to re-put in the datastore to a queue.

  We need to re-put the tests so that TestMetadata._pre_put_hook is run, so that
  the sheriff or alert threshold config of the TestMetadata is updated.

  Args:
    test_paths: List of test paths of tests to be re-put.
  """
  for start_index in range(0, len(test_paths), _MAX_TESTS_TO_PUT_AT_ONCE):
    group = test_paths[start_index:start_index + _MAX_TESTS_TO_PUT_AT_ONCE]
    urlsafe_keys = [utils.TestKey(t).urlsafe() for t in group]
    taskqueue.add(
        url='/put_entities_task',
        params={'keys': ','.join(urlsafe_keys)},
        queue_name=_TASK_QUEUE_NAME,
        countdown=_TASK_QUEUE_COUNTDOWN)
