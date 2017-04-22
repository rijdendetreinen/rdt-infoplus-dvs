FROM python:2.7-slim

COPY *.py /
COPY dvs-http.wsgi .
COPY requirements.txt .
COPY config/dvs-server.yaml config/dvs-server.yaml
COPY config/http.yaml config/http.yaml

RUN pip install -r requirements.txt
RUN pip install gunicorn

CMD [ "gunicorn", "dvs-http" ]
CMD [ "python", "dvs-daemon.py"]

EXPOSE 8120
EXPOSE 8140 
