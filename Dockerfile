FROM alpine/helm:4.2.1 as helm
RUN chown root:root /usr/bin/helm

FROM python:3-alpine

RUN mkdir -p /opt/pipe

COPY requirements.txt /opt/pipe
RUN pip install -r /opt/pipe/requirements.txt

COPY pipe /opt/pipe
COPY LICENSE.txt pipe.yml README.md /opt/pipe/

COPY --chown=root:root --from=helm /usr/bin/helm /usr/bin/helm

ENTRYPOINT ["python"]
CMD ["/opt/pipe/pipe.py"]
