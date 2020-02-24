# We use a container to set up the testing environment that we're going to use
# for the service tests.
FROM gcr.io/google-appengine/python

RUN virtualenv /env -p python3.7
ENV VIRTUAL_ENV /env
ENV PATH /env/bin:$PATH

# We need libre2-dev and pybind11 used for installing google-re2
RUN apt-get update && apt-get install -y libre2-dev && \
    pip install pybind11==2.4.3 && \
    export RE2_INCLUDES=$(python -c 'import pybind11; print(pybind11.get_include());') && \
    export CFLAGS="-I${RE2_INCLUDES} -std=c++11" && \
    pip install google-re2==0.0.4

# Add requirements.txt seperately for caching install result
ADD requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

# === Testing Enviroment Begin ===
ADD tests/requirements.txt /app/tests/requirements.txt
RUN pip install -r tests/requirements.txt

ARG emulator_host=datastore
ARG emulator_port=8888

ENV GAE_APPLICATION chromeperf
ENV GAE_SERVICE sheriff-config

ENV DATASTORE_DATASET chromeperf
ENV DATASTORE_PROJECT_ID chromeperf
ENV DATASTORE_EMULATOR_HOST $emulator_host:$emulator_port
ENV DATASTORE_EMULATOR_HOST_PATH $emulator_host:$emulator_port/datastore
# === Testing Enviroment End ===

ADD . /app

CMD python -m unittest discover -p 'test_*.py' -s /app
ENTRYPOINT ["/app/tests/entrypoint.sh"]
