FROM gcr.io/google-appengine/python

RUN virtualenv /env -p python3
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

ADD . /app

ENTRYPOINT gunicorn -b :$PORT main:APP --workers 6