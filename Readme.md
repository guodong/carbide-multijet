# Multijet Evaluation
## Quick Start
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