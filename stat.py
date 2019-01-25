import docker

client = docker.from_env()


def fib_count():
    with open('1755.r0.cch', 'r') as f:
        total = 0
        for line in f:
            arr = line.split()
            id = arr[0]
            c = client.containers.get(id)
            cmd = 'route -n'
            code, output = c.exec_run(cmd)
            size = len(output.split('\n'))
            total = total + size

        print total


def rule_count():
    with open('1755.r0.cch', 'r') as f:
        total = 0
        for line in f:
            arr = line.split()
            id = arr[0]
            c = client.containers.get(id)
            cmd = 'ovs-ofctl dump-flows s'
            code, output = c.exec_run(cmd)
            size = len(output.split('\n'))
            total = total + size
            print size

        print total


if __name__ == '__main__':
    rule_count()
