FROM ubuntu:latest
LABEL authors="bchat"

ENTRYPOINT ["top", "-b"]