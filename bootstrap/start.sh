#!/bin/bash
service openvswitch-switch start
ovs-vsctl add-br s
ovs-vsctl set-controller s tcp:172.17.0.1:6633
ovs-vsctl set-fail-mode s secure
# python /fpmserver/fpm/main.py
bash