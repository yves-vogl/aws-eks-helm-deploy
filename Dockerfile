FROM alpine/helm:3.8.1 as helm
RUN chown root:root /usr/bin/helm

FROM python:3.8-alpine3.15

RUN mkdir -p /opt/pipe

COPY requirements.txt /opt/pipe
RUN pip install -r /opt/pipe/requirements.txt

COPY pipe /opt/pipe
COPY LICENSE.txt pipe.yml README.md /opt/pipe/

COPY --chown=root:root --from=helm /usr/bin/helm /usr/bin/helm
RUN apk add git
RUN /usr/bin/helm plugin install https://github.com/jkroepke/helm-secrets --version v3.12.0
RUN wget -O sops https://github.com/mozilla/sops/releases/download/v3.7.2/sops-v3.7.2.linux.amd64 && chmod +x sops && mv sops /usr/bin/sops

ENTRYPOINT ["python"]
CMD ["/opt/pipe/pipe.py"]
