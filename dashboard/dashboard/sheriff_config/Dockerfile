FROM gcr.io/google-appengine/python

WORKDIR /sheriff-config
ADD ./ /sheriff-config

RUN virtualenv /env -p python3.7

RUN pip3 install -r requirements.txt

EXPOSE 80

CMD ['gunicorn', '-b', ':80', 'main:APP', '--workers', '2']
