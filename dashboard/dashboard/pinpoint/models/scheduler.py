# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Pinpoint Job Scheduler Module

This module implements a simple FIFO scheduler which in the future will be a
full-featured multi-dimensional priority queue based scheduler that leverages
more features of Swarming for managing the capacity of the Pinpoint swarming
pool.

"""

# TODO(dberris): Isolate the service that will make all the scheduling decisions
# and make this API a wrapper to the scheduler.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
from google.appengine.ext import ndb


# TODO(dberris): These models are temporary, when we move to using the service
# we'll use the google-cloud-datastore API directly.
class QueueElement(ndb.Model):
  """Models an element in a queues."""
  _default_indexed = False
  timestamp = ndb.DateTimeProperty(required=True, auto_now_add=True)
  job_id = ndb.StringProperty(required=True)
  status = ndb.StringProperty(
      required=True, default='Queued', choices=['Running', 'Done', 'Cancelled'])


class Queues(ndb.Model):
  """A root element for all queues."""
  pass


class ConfigurationQueue(ndb.Model):
  """Models a per-pool (configuration) FIFO queue."""
  _default_indexed = False
  _default_memcache = True
  jobs = ndb.StructuredProperty(QueueElement, repeated=True)
  configuration = ndb.StringProperty(required=True, indexed=True)

  @classmethod
  def GetOrCreateQueue(cls, configuration):
    parent = Queues.get_by_id('root')
    if not parent:
      parent = Queues(id='root')
      parent.put()

    queue = ConfigurationQueue.get_by_id(
        configuration, parent=ndb.Key('Queues', 'root'))
    if not queue:
      return ConfigurationQueue(
          jobs=[],
          configuration=configuration,
          id=configuration,
          parent=ndb.Key('Queues', 'root'))
    return queue

  @classmethod
  def AllQueues(cls):
    return cls.query(
        projection=[cls.configuration], ancestor=ndb.Key('Queues', 'root'))


class Error(Exception):
  pass


class QueueNotFound(Error):
  pass


@ndb.transactional
def Schedule(job):
  """Schedules a job for later execution.

  This function deduces the appropriate queue to which a fully-formed
  `dashboard.pinpoint.models.job.Job` must be enqueued, and persists a reference
  to the job ID to the queue for later execution.

  Arguments:
  - job: a fully-formed `dashboard.models.job.Job` instance.

  Raises:
  - ndb.TransactionFailedError when we fail to persist the queue
    transactionally.

  Returns None.
  """
  # Take a job and find an appropriate pool to enqueue it through.

  # 1. Use the configuration as the name of the pool.
  # TODO(dberris): Figure out whether a missing configuration is even valid.
  configuration = job.arguments.get('configuration', '(none)')

  # 2. Load the (potentially empty) FIFO queue.
  queue = ConfigurationQueue.GetOrCreateQueue(configuration)

  # TODO(dberris): Check whether we have too many elements in the queue,
  # and reject the attempt?

  # 3. Enqueue job according to insertion time.
  queue.jobs.append(QueueElement(job_id=job.job_id))
  queue.put()
  logging.debug('Scheduled: %r', queue)


@ndb.transactional
def PickJob(configuration):
  """Picks a job for execution for a given configuration.

  This returns the next eligible job to run which is one that's either already
  running, or one that's Queued.

  Returns a tuple (job_id, 'Running'|'Queued') if we have an eligible job to
  run, or (None, None).

  Arguments:
  - configuration: a configuration name, also used as a queue identifier.

  Raises:
  - ndb.TransactionFailedError when we fail to persist the queue
    transactionally.
  """
  # Load the FIFO queue for the configuration.
  queue = ConfigurationQueue.GetOrCreateQueue(configuration)
  logging.debug('Fetched: %r', queue)

  result = (None, None)
  if not queue.jobs:
    return result

  if queue.jobs[0].status == 'Running':
    return (queue.jobs[0].job_id, queue.jobs[0].status)

  # Remove all 'Done' and 'Cancelled' jobs.
  queue.jobs = [j for j in queue.jobs if j.status not in {'Done', 'Cancelled'}]
  for job in queue.jobs:
    # Pick the first job that's queued, and mark it 'Running'.
    if job.status == 'Queued':
      result = (job.job_id, job.status)
      job.status = 'Running'
      break

  # Persist the changes transactionally.
  queue.put()

  # Then return the result.
  return result


@ndb.transactional
def QueueStats(_):
  # Compute statistics for a FIFO queue given the configuration.
  # TODO(dberris): Implement this, when we expose this in the UI.
  pass


@ndb.transactional
def Cancel(job):
  """Marks a job for cancellation in the appropriate queue.

  This updates a job's status in the queue as cancelled, making it ineligible
  for running. This operation is not reversible.

  Arguments:
  - job: a fully-formed dashboard.pinpoint.models.job.Job instance.

  Raises:
  - ndb.TransactionFailedError on failure to transactionally update the queue.

  Returns None.
  """
  # Take a job and determine the FIFO Queue it's associated to.
  configuration = job.arguments.get('configuration', '(none)')

  # Find the job, and mark it cancelled.
  # TODO(dberris): Figure out whether a missing configuration is even valid.
  queue = ConfigurationQueue.GetOrCreateQueue(configuration)

  # We can only cancel 'Running' and 'Queued' jobs.
  for queued_job in queue.jobs:
    if queued_job.job_id == job.job_id:
      if queued_job.status in {'Running', 'Queued'}:
        queued_job.status = 'Cancelled'
        queue.put()
      return


@ndb.transactional
def Complete(job):
  """Marks a job completed in the appropriate queue.

  This updates a job's status in the queue as completed, making it ineligible
  for running. This operation is not reversible.

  Arguments:
  - job: a fully-formed dashboard.pinpoint.models.job.Job instance.

  Raises:
  - ndb.TransactionFilaedError on failure to transactionally update the queue.

  Returns None.
  """
  # TODO(dberris): Figure out whether a missing configuration is even valid.
  configuration = job.arguments.get('configuration', '(none)')

  queue = ConfigurationQueue.GetOrCreateQueue(configuration)

  # Remove all 'Done' and 'Cancelled' jobs.
  queue.jobs = [j for j in queue.jobs if j.status not in {'Done', 'Cancelled'}]

  # We can only complete 'Running' jobs.
  for queued_job in queue.jobs:
    if queued_job.job_id == job.job_id:
      if queued_job.status == 'Running':
        queued_job.status = 'Done'
        queue.put()
      return


@ndb.transactional
def Remove(configuration, job_id):
  """Forcibly removes a job from the queue, by ID.

  This updates the queue to remove the job identifier. Note that this does not
  update a job's status. This is mostly a convenience method to forcibly remove
  jobs from a queue as a remedial action.

  Arguments:
  - configuration: a string identifying the configuration, used as a queue
    identifier as well.
  - job_id: a string identifying a job instance.

  Raises:
  - ndb.TransactionFilaedError on failure to transactionally update the queue.

  Returns None
  """
  queue = ConfigurationQueue.GetOrCreateQueue(configuration)
  queue.jobs = [j for j in queue.jobs if j.job_id != job_id]
  queue.put()


@ndb.transactional
def AllConfigurations():
  return [q.configuration for q in ConfigurationQueue.AllQueues().fetch()]
