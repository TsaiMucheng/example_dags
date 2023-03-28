FROM apache/airflow:2.2.4
USER root
ARG USER_HOME=/home/airflow
ENV TZ=Asia/Taipei
ENV LANG=zh_TW.UTF-8
ENV LANGUAGE=zh_TW.UTF-8

RUN sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list' \
  && apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys  78BD65473CB3BD13

RUN apt-get update \
  && apt-get install -y --no-install-recommends make build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm libncurses5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev \
  && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
  && apt-get install -y --no-install-recommends iputils-ping telnet nano git google-chrome-stable \
  && apt-get autoremove -yqq --purge \
  && apt-get install -y zip \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

# Insatll chromedriver
RUN wget -O /tmp/chromedriver.zip http://chromedriver.storage.googleapis.com/`curl -sS chromedriver.storage.googleapis.com/LATEST_RELEASE`/chromedriver_linux64.zip \
  && unzip /tmp/chromedriver.zip chromedriver -d /usr/bin/ \
  && rm /tmp/chromedriver.zip

USER airflow
WORKDIR ${AIRFLOW_HOME}/env/
COPY ./env/extension.txt ./
# COPY ./env/environment.yml ./env/extension.txt ./env/requirements.txt ./
# RUN chown -R airflow: ${AIRFLOW_HOME}
# RUN cat extension.txt
# RUN ls | grep environment
RUN which pip
RUN pip install --no-cache-dir -r extension.txt

# Install miniconda
USER root
RUN wget --quiet https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda.sh \
  && /bin/bash ~/miniconda.sh -b -p /opt/conda
ENV PATH=/opt/conda/bin:$PATH
# RUN conda env create -f "./environment.yml"
RUN echo $PATH
RUN which pip

# Solve mongo hook signing in the original string were escaped unless they were included in safe
COPY ./env/mongo.py ${USER_HOME}/.local/lib/python3.7/site-packages/airflow/providers/mongo/hooks/
RUN chown -R airflow: ${AIRFLOW_HOME}

USER airflow
# SHELL ["conda", "run", "-n", "${testenv}", "/bin/bash", "-c"]
# RUN pip3 install --upgrade pip
# RUN pip3 install --no-cache-dir -r requirements.txt
WORKDIR ${AIRFLOW_HOME}