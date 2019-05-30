# We use a container to set up the testing environment that we're going to use
# for the service tests.
FROM gcr.io/google-appengine/python

WORKDIR /sheriff-config
ADD . /sheriff-config

RUN virtualenv /env -p python3.7
RUN . /env/bin/activate && pip3 install -r requirements.txt
RUN . /env/bin/activate && pip3 install -r tests/requirements.txt

ARG emulator_host=datastore
ARG emulator_port=8888

ENV GAE_APPLICATION chromeperf
ENV GAE_SERVICE sheriff-config

ENV DATASTORE_DATASET chromeperf
ENV DATASTORE_PROJECT_ID chromeperf
ENV DATASTORE_EMULATOR_HOST $emulator_host:$emulator_port
ENV DATASTORE_EMULATOR_HOST_PATH $emulator_host:$emulator_port/datastore
ENV DATASTORE_HOST http://$emulator_host:$emulator_port

# By default we run all the unit tests, and any end-to-end tests we might have.
CMD . /env/bin/activate && \
        python3.7 -m unittest discover -p '*_test.py' -s /sheriff-config && \
        python3.7 -m unittest discover -p 'test_*.py' -s /sheriff-config
