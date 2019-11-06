#!/bin/bash
source ~/App/gnuplot/env.sh

if [ x$1 == 'x' ]; then
    echo "error args";
    exit
fi

scp pcl:/tmp/data.txt  data-$1
scp pcl:/tmp/data-fpm  data-fpm-$1
scp pcl:/tmp/data-fpm-line data-fpm-line-$1

# gnuplot $1.gp
# gnuplot $1-fpm.gp
