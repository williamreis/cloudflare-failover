FROM python:3.11-slim

WORKDIR /src

COPY src/*requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

ARG FLASK_ENV
RUN if [ "$FLASK_ENV" = "dev" ] ; then pip install --no-cache-dir -r dev-requirements.txt ; fi

COPY ./src .

CMD ["python3", "main.py"]