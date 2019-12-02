#!/bin/bash
if [ -L $0 ]
then 
    BASE_DIR=`dirname $(readlink $0)`
else 
    BASE_DIR=`dirname $0`
fi    
basepath=$(cd $BASE_DIR/../; pwd)
# echo $basepath

cd $basepath

docker run -it --rm -v $basepath:$basepath --name ryufly_controller snlab/ryufly $basepath/ryufly/run.sh
