#!/bin/bash
source ~/App/gnuplot/env.sh

gnuplot plot-flood.gplt
gnuplot plot-fpm-flood.gplt
gnuplot plot-pp.gplt
gnuplot plot-fpm-pp.gplt
