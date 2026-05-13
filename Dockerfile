FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends default-jdk-headless procps bash && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
COPY data_engineering/requirements.txt ./data_engineering/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r data_engineering/requirements.txt

RUN python -m spacy download en_core_web_sm
RUN python -m nltk.downloader stopwords

EXPOSE 8888

ENV JUPYTER_ENABLE_LAB=yes

CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root", "--notebook-dir=/app", "--ServerApp.token=''", "--ServerApp.disable_check_xsrf=True"]
