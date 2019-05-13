FROM python:3.7-alpine
FROM grpc/python:latest

WORKDIR /sheriff-config
ADD ./ /sheriff-config


RUN pip install -r requirements.txt

EXPOSE 80

CMD ['gunicorn', '-b', ':80', 'main:APP', '--workers', '2']
