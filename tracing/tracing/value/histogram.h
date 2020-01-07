// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <memory>
#include <string>
#include <vector>

#include "tracing/tracing/proto/histogram.pb.h"

namespace catapult {

class RunningStatistics;

// This class continuously saves results from a performance tests.
// You can later convert the results to a proto and upload to a Catapult
// dashboard.
//
// This class provides a subset of the API in histogram.py and is meant to work
// exactly the same way.
class HistogramBuilder {
 public:
  HistogramBuilder(const std::string& name,
                   tracing::tracing::proto::UnitAndDirection unit);
  ~HistogramBuilder();

  void set_description(const std::string& description) {
    description_ = description;
  }

  void AddSample(float value);

  std::unique_ptr<tracing::tracing::proto::Histogram> toProto() const;

 private:
  class Resampler;

  std::unique_ptr<Resampler> resampler_;
  std::unique_ptr<RunningStatistics> running_statistics_;
  int max_num_sample_values_;
  std::string name_;
  std::string description_;
  tracing::tracing::proto::UnitAndDirection unit_;
  std::vector<float> sample_values_;
  int num_nans_;
};

}  // namespace catapult
