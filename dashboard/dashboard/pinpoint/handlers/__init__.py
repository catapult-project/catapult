# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from dashboard.pinpoint.handlers.cancel import Cancel
from dashboard.pinpoint.handlers.config import Config
from dashboard.pinpoint.handlers.commit import Commit
from dashboard.pinpoint.handlers.commits import Commits
from dashboard.pinpoint.handlers.fifo_scheduler import FifoScheduler
from dashboard.pinpoint.handlers.isolate import Isolate
from dashboard.pinpoint.handlers.isolate import IsolateCleanup
from dashboard.pinpoint.handlers.job import Job
from dashboard.pinpoint.handlers.jobs import Jobs
from dashboard.pinpoint.handlers.migrate import Migrate
from dashboard.pinpoint.handlers.new import New
from dashboard.pinpoint.handlers.queue_stats import QueueStats
from dashboard.pinpoint.handlers.refresh_jobs import RefreshJobs
from dashboard.pinpoint.handlers.results2 import Results2
from dashboard.pinpoint.handlers.results2 import Results2Generator
from dashboard.pinpoint.handlers.run import Run
from dashboard.pinpoint.handlers.stats import Stats
from dashboard.pinpoint.handlers.task_updates import TaskUpdates
