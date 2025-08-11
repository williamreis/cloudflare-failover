FROM python:3.11-slim

WORKDIR /app

COPY src/*requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

ARG FLASK_ENV
RUN if [ "$FLASK_ENV" = "dev" ] ; then pip install --no-cache-dir -r dev-requirements.txt ; fi

COPY ./src ./src

# Altere esta linha para executar como um módulo
CMD ["python3", "-m", "src.main"]
