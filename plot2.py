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

x1, y1 = load_data('/home/yutao/tmp/flood.log')
x2, y2 = load_data('/home/yutao/tmp/pp.log')

plt.plot(x1,y1)
plt.plot(x2,y2)
plt.show()
