FROM python:bullseye
COPY app /app
RUN adduser --gecos "" --disabled-password user
USER user
ENV PATH="${PATH}:/home/user/.local/bin"
WORKDIR /app
CMD ["flask", "run", "-p", "5000", "-h", "0.0.0.0"]
