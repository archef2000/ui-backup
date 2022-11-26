FROM python:bullseye
COPY app /app
WORKDIR /app
RUN adduser --gecos "" --disabled-password user \
    && pip install -r requirements.txt
USER user
ENV PATH="${PATH}:/home/user/.local/bin"
CMD ["flask", "run", "-p", "5000", "-h", "0.0.0.0"]
