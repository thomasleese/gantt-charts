FROM python:3.5

# create user first
RUN groupadd -r ganttcharts && useradd -r -g ganttcharts ganttcharts

# gosu
RUN gpg --keyserver pool.sks-keyservers.net --recv-keys B42F6819007F00F88E364FD4036A9C25BF357DD4
RUN curl -o /usr/local/bin/gosu -SL "https://github.com/tianon/gosu/releases/download/1.2/gosu-$(dpkg --print-architecture)" \
    && curl -o /usr/local/bin/gosu.asc -SL "https://github.com/tianon/gosu/releases/download/1.2/gosu-$(dpkg --print-architecture).asc" \
    && gpg --verify /usr/local/bin/gosu.asc \
    && rm /usr/local/bin/gosu.asc \
    && chmod +x /usr/local/bin/gosu

# Node, NPM and Bower
RUN apt-get update && apt-get install -y nodejs nodejs-legacy npm
RUN npm install -g bower grunt-cli

# Cairo
RUN apt-get update && apt-get install -y libcairo2-dev

# Gantt Charts
RUN mkdir /code
WORKDIR /code
COPY requirements.txt /code/
RUN pip install -r requirements.txt
COPY bower.json /code/
COPY .bowerrc /code/
RUN bower install --allow-root --force && \
    cd ganttcharts/web/static/bower_components/bootstrap && \
    npm install
COPY ganttcharts/web/static/bootstrap_variables.scss ganttcharts/web/static/bower_components/bootstrap/scss/_variables.scss
RUN cd ganttcharts/web/static/bower_components/bootstrap && \
    grunt dist
COPY . /code
RUN pip install -e .

WORKDIR /code

COPY docker-entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]

EXPOSE 8000
CMD ["gunicorn", "ganttcharts.web:app", "--access-logfile", "-", "--error-logfile", "-", "--bind", "0.0.0.0:8000"]
