FROM gcr.io/google_appengine/python-compat
ADD . /app

# Debian 7 doesn't have the right version of glibc, so we need to install.
# Ideally at some point, instead of using the appengine supplied python
# image, we could image our own ubuntu version.
# https://github.com/GoogleCloudPlatform/appengine-python-vm-runtime
RUN apt-get update && apt-get install -y git libglib2.0-dev procps
RUN sed -i '1ideb http://ftp.debian.org/debian experimental main' /etc/apt/sources.list
RUN apt-get update && apt-get -y -t experimental install libc6

RUN (cd /; git clone https://github.com/catapult-project/catapult.git)
