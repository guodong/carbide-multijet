import json

from matplotlib import pyplot as plt


def load_data(path):
    with open(path) as f:
        data = json.load(f)

    y=[]
    x=[]

    for item in data:
        y.append(float(item['delta']))
        x.append(int(item['num']))
    return x,y

x1, y1 = load_data('/home/yutao/tmp/flood-node.log')
x2, y2 = load_data('/home/yutao/tmp/pp-node.log')

plt.grid()


def plot1(xx1, yy1, xx2, yy2):
    plt.plot(xx1, yy1, 'r', label='Flood')
    plt.plot(xx2, yy2, 'b', label='PushPullNeighbor')
    plt.legend()
    plt.xlabel('Update sequence number')
    plt.ylabel('Convergence time (s)')
    plt.title('Convergence time of network')

    plt.show()

# for i in range(3):
#     xx1 = x1[i::3]
#     yy1 = y1[i::3]
#     xx2 = x2[i::3]
#     yy2 = y2[i::3]
#     plot1(xx1, yy1, xx2, yy2)


plot1(x1, y1, x2, y2)