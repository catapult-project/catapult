# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import math


# This should be equal to sys.float_info.max, but that value might differ
# between platforms, whereas ECMA Script specifies this value for all platforms.
# The specific value should not matter in normal practice.
JS_MAX_VALUE = 1.7976931348623157e+308


# Converts the given percent to a string in the following format:
# 0.x produces '0x0',
# 0.xx produces '0xx',
# 0.xxy produces '0xx_y',
# 1.0 produces '100'.
def PercentToString(percent):
  if percent < 0 or percent > 1:
    raise Exception('percent must be in [0,1]')
  if percent == 0:
    return '000'
  if percent == 1:
    return '100'
  s = str(percent)
  if s[1] != '.':
    raise Exception('Unexpected percent')
  s += '0' * max(4 - len(s), 0)
  if len(s) > 4:
    s = s[:4] + '_' + s[4:]
  return '0' + s[2:]


class Range(object):
  def __init__(self):
    self._empty = True
    self._min = None
    self._max = None

  @staticmethod
  def FromExplicitRange(lower, upper):
    r = Range()
    r._min = lower
    r._max = upper
    r._empty = False
    return r

  @property
  def empty(self):
    return self._empty

  @property
  def min(self):
    return self._min

  @property
  def max(self):
    return self._max

  @property
  def center(self):
    return (self._min + self._max) * 0.5

  def AddValue(self, x):
    if self._empty:
      self._empty = False
      self._min = x
      self._max = x
      return

    self._max = max(x, self._max)
    self._min = min(x, self._min)


# This class computes statistics online in O(1).
class RunningStatistics(object):
  def __init__(self):
    self._mean = 0
    self._count = 0
    self._max = -JS_MAX_VALUE
    self._min = JS_MAX_VALUE
    self._sum = 0
    self._variance = 0
    # Mean of logarithms of samples, or undefined if any samples were <= 0.
    self._meanlogs = 0

  @property
  def count(self):
    return self._count

  @property
  def geometric_mean(self):
    if self._meanlogs is None:
      return None
    return math.exp(self._meanlogs)

  @property
  def mean(self):
    if self._count == 0:
      return None
    return self._mean

  @property
  def max(self):
    return self._max

  @property
  def min(self):
    return self._min

  @property
  def sum(self):
    return self._sum

  @property
  def variance(self):
    if self.count == 0:
      return None
    if self.count == 1:
      return 0
    return self._variance / (self.count - 1)

  @property
  def stddev(self):
    if self.count == 0:
      return None
    return math.sqrt(self.variance)

  def Add(self, x):
    self._count += 1
    self._max = max(self._max, x)
    self._min = min(self._min, x)
    self._sum += x

    if x <= 0:
      self._meanlogs = None
    elif self._meanlogs is not None:
      self._meanlogs += (math.log(abs(x)) - self._meanlogs) / self.count

    # The following uses Welford's algorithm for computing running mean and
    # variance. See http://www.johndcook.com/blog/standard_deviation.
    if self.count == 1:
      self._mean = x
      self._variance = 0
    else:
      old_mean = self._mean
      old_variance = self._variance

      # Using the 2nd formula for updating the mean yields better precision but
      # it doesn't work for the case oldMean is Infinity. Hence we handle that
      # case separately.
      if abs(old_mean) == float('inf'):
        self._mean = self._sum / self.count
      else:
        self._mean = old_mean + float(x - old_mean) / self.count
      self._variance = old_variance + (x - old_mean) * (x - self._mean)

  def Merge(self, other):
    result = RunningStatistics()
    result._count = self._count + other._count
    result._sum = self._sum + other._sum
    result._min = min(self._min, other._min)
    result._max = max(self._max, other._max)
    if result._count == 0:
      result._mean = 0
      result._variance = 0
      result._meanlogs = 0
    else:
      # Combine the mean and the variance using the formulas from
      # https://goo.gl/ddcAep.
      result._mean = float(result._sum) / result._count
      delta_mean = (self._mean or 0) - (other._mean or 0)
      result._variance = self._variance + other._variance + (
          self._count * other._count * delta_mean * delta_mean / result._count)

      # Merge the arithmetic means of logarithms of absolute values of samples,
      # weighted by counts.
      if self._meanlogs is None or other._meanlogs is None:
        result._meanlogs = None
      else:
        result._meanlogs = (self._count * self._meanlogs +
                            other._count * other._meanlogs) / result._count
    return result

  def AsDict(self):
    if self._count == 0:
      return []
    # It's more efficient to serialize these fields in an array. If you add any
    # other fields, you should re-evaluate whether it would be more efficient to
    # serialize as a dict.
    return [
        self._count,
        self._max,
        self._meanlogs,
        self._mean,
        self._min,
        self._sum,
        self._variance,
    ]

  @staticmethod
  def FromDict(dct):
    result = RunningStatistics()
    if len(dct) != 7:
      return result
    [result._count, result._max, result._meanlogs, result._mean, result._min,
     result._sum, result._variance] = dct
    return result
