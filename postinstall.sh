#!/bin/bash

set -e

bower install --quiet

pushd ganttcharts/web/static/bower_components/bootstrap
npm install --silent
npm install --only=dev --silent  # for grunt stuff
popd

cp ganttcharts/web/static/bootstrap_variables.scss ganttcharts/web/static/bower_components/bootstrap/scss/_variables.scss

pushd ganttcharts/web/static/bower_components/bootstrap
grunt dist
popd
