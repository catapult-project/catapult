# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import optparse
import re

from telemetry.core import command_line


def HasLabelIn(obj, labels):
  for label in labels:
    if hasattr(obj, label) and getattr(obj, label):
      return True
  return False


class PageFilter(command_line.ArgumentHandlerMixIn):
  """Filters pages in the page set based on command-line flags."""

  @classmethod
  def AddCommandLineArgs(cls, parser):
    group = optparse.OptionGroup(parser, 'Page filtering options')
    group.add_option('--page-filter',
        help='Use only pages whose URLs match the given filter regexp.')
    group.add_option('--page-filter-exclude',
        help='Exclude pages whose URLs match the given filter regexp.')
    group.add_option('--page-label-filter',
        help='Use only pages that have any of these labels')
    group.add_option('--page-label-filter-exclude',
        help='Exclude pages that have any of these labels')

    parser.add_option_group(group)

  @classmethod
  def ProcessCommandLineArgs(cls, parser, args):
    cls._page_regex = None
    cls._page_exclude_regex = None
    cls._include_labels = None
    cls._exclude_labels = None

    if args.page_filter:
      try:
        cls._page_regex = re.compile(args.page_filter)
      except re.error:
        raise parser.error('--page-filter: invalid regex')

    if args.page_filter_exclude:
      try:
        cls._page_exclude_regex = re.compile(args.page_filter_exclude)
      except re.error:
        raise parser.error('--page-filter-exclude: invalid regex')

    if args.page_label_filter:
      cls._include_labels = args.page_label_filter.split(',')

    if args.page_label_filter_exclude:
      cls._exclude_labels = args.page_label_filter_exclude.split(',')

  @classmethod
  def IsSelected(cls, page):
    # Exclude filters take priority.
    if cls._exclude_labels and HasLabelIn(page, cls._exclude_labels):
      return False
    if cls._page_exclude_regex:
      matches_url = cls._page_exclude_regex.search(page.url)
      matches_name = page.name and cls._page_exclude_regex.search(page.name)
      if matches_url or matches_name:
        return False

    # Apply all filters.
    filter_result = True
    if cls._include_labels:
      filter_result = filter_result and HasLabelIn(page, cls._include_labels)
    if cls._page_regex:
      matches_url = cls._page_regex.search(page.url)
      matches_name = page.name and cls._page_regex.search(page.name)
      filter_result = filter_result and (matches_url or matches_name)

    return filter_result
