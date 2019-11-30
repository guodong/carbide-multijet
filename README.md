# Multijet Evaluation

## eval

```
sudo python eval3.py test.cch

> start_ospf_and_server

> eval

```




## Quick Start

1. start evaluation shell

    sudo python eval2.py xxxx.cch

> must run at this directory; if `configs/common/pp` file exists, system use PushPull algorithm, else use Flood algorithm

2. some evaluation commands

```
start_ryu2     # start main multijet process
kill_ryu       # kill multijet process
eval           # evaluation: install all ospf rules
eval2          # evaluation: install a path, delete rule, add rule
start_ospf_and_server
kill_ospf_and_server
```


## Project structure

```
├── eval2.py   # evaluation script, start evaluation shell
├── plot2.py   # plot script, plot related result
├── fpm        # fpm server, run in container
|   ├── fpm_pb2.py
|   ├── fpm.proto
|   ├── fpm.py
|   ├── main.py
|   ├── qpb_pb2.py
|   └── qpb.proto
├── multijet
    ├── core
    │   ├── Space.py    # unused
    ├── ecs_mgr.py      # ECS manager include FloodECSMgr and PushPullECSMgr
    ├── multijet2.py    # Ryu application, implement packet transceiver by OpenFlow API
    ├── topo.py         # topology utility
    ├── transceiver.py  # layered message transceiver encapsulation
    ├── utils.py        # log utility
    ├── verifier_mock2.py   #  mock test script

```



## deprecated

### Start rocketfuel topology
> Make sure you have no less than 12GB memory
```commandline
$ sudo python topo.py
```

### Tiny Topo with 4 routers
```commandline
$ sudo python topo.py test.cch
```

## Multijet CLI

Fetch rules from ovs:
```commandline
multijet> fetch rules
```

Do verification:
```commandline
multijet> verify
```

Cat the logs of multijet:

Multijet logs are stored in `/etc/quagga/multijetlog` which is a mounted dir from `configs/{container_id}`