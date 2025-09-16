FROM python:3.9-slim-buster

COPY app /app
COPY requirements.txt /app/requirements.txt

WORKDIR /app

RUN pip3 install -r requirements.txt

EXPOSE 5555

ENV PYTHONPATH "/app/"
ENV PYTHONUNBUFFERED 1

CMD [ "python3", "physical_twin_emulator.py", "-c", "emulator_conf.yaml" ]
