# Copyright (c) 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from apache_beam.options.pipeline_options import PipelineOptions


class BqExportOptions(PipelineOptions):

  @classmethod
  def _add_argparse_args(cls, parser):  # pylint: disable=invalid-name
    parser.add_argument(
        '--end_date',
        help=('Last day of data to export in YYYYMMDD format.  '
              'No value means today.'),
        default=None)
    parser.add_argument(
        '--num_days', help='Number of days data to export', type=int, default=1)
