#!/bin/bash
if [ -L $0 ]
then 
    BASE_DIR=`dirname $(readlink $0)`
else 
    BASE_DIR=`dirname $0`
fi    
basepath=$(cd $BASE_DIR/../; pwd)
# echo $basepath

export PYTHONPATH=$basepath
cd $basepath

rm -f $basepath/configs/common/ryufly.log

# ryu-manager --log-file $basepath/configs/common/ryufly.log --nouse-stderr  ryufly.fly
ryu-manager --log-config-file $basepath/ryufly/log.config ryufly.fly
