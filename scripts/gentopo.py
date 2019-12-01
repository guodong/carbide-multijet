import random
from math import sqrt
import networkx as nx
import matplotlib.pyplot as plt
import json


def gen_topo(n):
    G = nx.gnp_random_graph(n, 0.12, 1)
    nx.draw(G, with_labels=True)
    plt.show()
    result = {}

    for i in range(n):
        result[str(i)] = {'neighbor': []}
    for e in G.edges:
        result[str(e[0])]['neighbor'].append(str(e[1]))
        result[str(e[1])]['neighbor'].append(str(e[0]))

    print result
    with open('gentopo.out.json', 'w') as f:
        f.write(json.dumps(result))


gen_topo(32)


def draw_graph(nodes):
    G = nx.Graph()
    for id, nei in nodes.items():
        G.add_node(id)
        for ne in nei['neighbor']:
            G.add_edge(id, ne)
    nx.draw(G, with_labels=True)
    plt.show()


def get_ordered_list(points, x, y):
    points.sort(key=lambda p: sqrt((p['coor'][0] - x) ** 2 + (p['coor'][1] - y) ** 2))
    return points


def gen_topo1(n_nodes, n_least_link, n_most_link):
    size = n_nodes * n_nodes
    nodes = [{'id': i, 'coor': (random.randint(0, size), random.randint(0, size))} for i in range(n_nodes)]
    copy = nodes[:]
    print nodes
    result = {}
    for n in nodes:
        nei_count = random.randint(n_least_link, n_most_link)
        ord_points = get_ordered_list(copy, n['coor'][0], n['coor'][1])
        print n['id']
        result[n['id']] = {'neighbor': [on['id'] for on in ord_points[1:]][:nei_count]}
        print n['id']
        print result

    draw_graph(result)

# gen_topo1(1, 1, 3)
