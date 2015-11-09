#!/bin/bash

set -e

bower install

pushd ganttcharts/web/static/bower_components/bootstrap
npm install
npm install --only=dev  # for grunt stuff
popd

cp ganttcharts/web/static/bootstrap_variables.scss ganttcharts/web/static/bower_components/bootstrap/scss/_variables.scss

pushd ganttcharts/web/static/bower_components/bootstrap
grunt dist
popd
