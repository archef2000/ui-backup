FROM python:bullseye
RUN adduser --gecos "" --disabled-password user
USER user
ENV PATH="${PATH}:/home/user/.local/bin"
CMD ["flask", "run", "-p", "5000", "-h", "0.0.0.0"]