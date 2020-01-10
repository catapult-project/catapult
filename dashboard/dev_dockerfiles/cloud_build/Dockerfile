FROM google/cloud-sdk:272.0.0

ARG PROTOBUF_VERSION=3.6.1.3-2
ARG SOURCE_DIR=.

# The latest version is in sid repo. So need to specify the
# version of dependency to avoid version conflix if you want
# to use "stable" one.
RUN apt-get install -y \
  libprotoc17=${PROTOBUF_VERSION} \
  protobuf-compiler=${PROTOBUF_VERSION} \
  make

ENV PYTHONPATH=/usr/lib/google-cloud-sdk/platform/google_appengine

# Copy the sources into the workdir, at build time.
ADD ${SOURCE_DIR} /catapult

# TODO(fancl): Figure out if we can remove this work-around later.
# It turns out, running the tests need to install git hooks.
# Instead of removing that part, we instead fake the fact that we have a .git
# directory.
RUN mkdir -p /catapult/.git/hooks
WORKDIR /catapult/dashboard

# Ensure that the protobufs are always built.
RUN make -C dashboard
