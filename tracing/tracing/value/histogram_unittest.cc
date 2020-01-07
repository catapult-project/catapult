// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "tracing/tracing/value/histogram.h"

#include <cmath>
#include <sstream>

#include "testing/gtest/include/gtest/gtest.h"
#include "tracing/tracing/proto/histogram.pb.h"

namespace catapult {

namespace proto = tracing::tracing::proto;

proto::UnitAndDirection UnitWhatever() {
  proto::UnitAndDirection unit;
  unit.set_unit(proto::UNITLESS);
  unit.set_improvement_direction(proto::NOT_SPECIFIED);
  return unit;
}

TEST(HistogramTest, WritesCorrectNameToProto) {
  HistogramBuilder builder("my name", UnitWhatever());

  auto histogram = builder.toProto();

  EXPECT_EQ(histogram->name(), "my name");
}

TEST(HistogramTest, WritesCorrectDescriptionToProto) {
  HistogramBuilder builder("", UnitWhatever());

  builder.set_description("desc!");

  auto histogram = builder.toProto();

  EXPECT_EQ(histogram->description(), "desc!");
}

TEST(HistogramTest, WritesCorrectUnitToProto) {
  proto::UnitAndDirection unit;
  unit.set_unit(proto::TS_MS);
  unit.set_improvement_direction(proto::BIGGER_IS_BETTER);
  HistogramBuilder builder("", unit);

  auto histogram = builder.toProto();

  EXPECT_EQ(histogram->unit().unit(), proto::TS_MS);
  EXPECT_EQ(histogram->unit().improvement_direction(), proto::BIGGER_IS_BETTER);
}

TEST(HistogramTest, WritesSmallNumberOfSamplesToProtoInOrder) {
  HistogramBuilder builder("", UnitWhatever());

  builder.AddSample(1.0);
  builder.AddSample(2.0);
  builder.AddSample(3.0);
  builder.AddSample(4.0);

  auto histogram = builder.toProto();

  EXPECT_EQ(histogram->sample_values_size(), 4);
  EXPECT_EQ(histogram->sample_values(0), 1.0);
  EXPECT_EQ(histogram->sample_values(1), 2.0);
  EXPECT_EQ(histogram->sample_values(2), 3.0);
  EXPECT_EQ(histogram->sample_values(3), 4.0);
}

TEST(HistogramTest, StartsUniformlySamplingAfterReachingMaxNumSamples) {
  HistogramBuilder builder("", UnitWhatever());

  for (int i = 0; i < 100; ++i) {
    builder.AddSample(i);
  }

  auto histogram = builder.toProto();

  EXPECT_EQ(histogram->sample_values_size(), 10)
      << "Did not expect num samples to grow beyond 10, which is the default "
      << "max number of samples";

  // Values will get randomly thrown away, but do some spot checks that they
  // at least are in range.
  ASSERT_LE(0, histogram->sample_values(0));
  ASSERT_GE(99, histogram->sample_values(0));
  ASSERT_LE(0, histogram->sample_values(1));
  ASSERT_GE(99, histogram->sample_values(1));
  ASSERT_LE(0, histogram->sample_values(9));
  ASSERT_GE(99, histogram->sample_values(9));
}

TEST(HistogramTest, WritesCorrectRunningStatisticsToProto) {
  HistogramBuilder builder("", UnitWhatever());

  builder.AddSample(10.0);
  builder.AddSample(20.0);
  builder.AddSample(30.0);
  builder.AddSample(40.0);

  auto histogram = builder.toProto();

  EXPECT_EQ(histogram->running().count(), 4);
  EXPECT_EQ(histogram->running().max(), 40.0);
  EXPECT_FLOAT_EQ(histogram->running().meanlogs(), 3.0970986);
  EXPECT_EQ(histogram->running().mean(), 25.0);
  EXPECT_EQ(histogram->running().min(), 10.0);
  EXPECT_EQ(histogram->running().sum(), 100.0);
  EXPECT_FLOAT_EQ(histogram->running().variance(), 166.6667);
}

TEST(HistogramTest, DoesNotWriteMeanlogsIfNegativeSampleAdded) {
  HistogramBuilder builder("", UnitWhatever());

  builder.AddSample(20.0);
  builder.AddSample(-1.0);

  auto histogram = builder.toProto();

  ASSERT_EQ(histogram->running().meanlogs(), 0);
}

}  // namespace catapult

