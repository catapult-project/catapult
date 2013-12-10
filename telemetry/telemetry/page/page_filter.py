# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import optparse
import re

def HasLabelIn(obj, labels):
  for label in labels:
    if hasattr(obj, label) and getattr(obj, label):
      return True
  return False


class PageFilter(object):
  """Filters pages in the page set based on command line flags."""

  def __init__(self, options):
    if options.page_filter:
      try:
        self._page_regex = re.compile(options.page_filter)
      except re.error:
        raise Exception('--page-filter: invalid regex')
    else:
      self._page_regex = None

    if options.page_filter_exclude:
      try:
        self._page_exclude_regex = re.compile(options.page_filter_exclude)
      except re.error:
        raise Exception('--page-filter-exclude: invalid regex')
    else:
      self._page_exclude_regex = None

    self._include_labels = None
    self._exclude_labels = None
    if options.page_label_filter:
      self._include_labels = options.page_label_filter.split(',')
    if options.page_label_filter_exclude:
      self._exclude_labels = options.page_label_filter_exclude.split(',')

  def IsSelected(self, page):
    # Exclude filters take priority
    if self._exclude_labels and HasLabelIn(page, self._exclude_labels):
      return False
    if self._page_exclude_regex and (
        self._page_exclude_regex.search(page.url) or
        (page.name and self._page_exclude_regex.search(page.name))):
      return False
    # Apply all filters
    filter_result = True
    if self._include_labels:
      filter_result = filter_result and HasLabelIn(page, self._include_labels)
    if self._page_regex:
      filter_result = filter_result and (
          self._page_regex.search(page.url) or
          (page.name and self._page_regex.search(page.name)))
    return filter_result

  @staticmethod
  def AddCommandLineOptions(parser):
    group = optparse.OptionGroup(parser, 'Page filtering options')
    group.add_option('--page-filter', dest='page_filter',
        help='Use only pages whose URLs match the given filter regexp.')
    group.add_option('--page-filter-exclude', dest='page_filter_exclude',
        help='Exclude pages whose URLs match the given filter regexp.')
    group.add_option('--page-label-filter', dest='page_label_filter',
        help='Use only pages that have any of these labels')
    group.add_option('--page-label-filter-exclude',
        dest='page_label_filter_exclude',
        help='Exclude pages that have any of these labels')

    parser.add_option_group(group)
