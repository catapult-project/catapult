// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <cmath>
#include <limits>

namespace catapult {

class RunningStatistics {
 public:
  RunningStatistics()
      : count_(0), mean_(0.0),
        max_(std::numeric_limits<float>::min()),
        min_(std::numeric_limits<float>::max()),
        sum_(0.0), variance_(0.0), meanlogs_(0.0), meanlogs_valid_(true) {}

  void Add(float value);

  int count() const { return count_;}
  float mean() const { return mean_;}
  float max() const { return max_;}
  float min() const { return min_;}
  float sum() const { return sum_;}
  float variance() const;
  float meanlogs() const;
  bool meanlogs_valid() const { return meanlogs_valid_; }

 private:
  int count_;
  float mean_;
  float max_;
  float min_;
  float sum_;
  float variance_;
  float meanlogs_;  // Mean of logarithms of samples.
  bool meanlogs_valid_;
};

}  // namespace catapult
