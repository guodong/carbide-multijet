#!/bin/bash

if [ x$1 == 'x' ]; then
    echo "error args";
    exit
fi


cp fig-flood-fpm.eps $1-fig-flood-fpm.eps
cp fig-flood.eps $1-fig-flood.eps
cp fig-pp-fpm.eps $1-fig-pp-fpm.eps
cp fig-pp.eps $1-fig-pp.eps
