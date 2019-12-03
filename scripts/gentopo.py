import random
from math import sqrt
import networkx as nx
import matplotlib.pyplot as plt
import json


def gen_topo(n):
    # G = nx.fast_gnp_random_graph(n, 0.132, 1)
    G = nx.fast_gnp_random_graph(n, 132, 1)
    topo = {
        'nodes': [],
        'links': []
    }
    for no in G.nodes:
        topo['nodes'].append(no)
    for e in G.edges:
        topo['links'].append(e)
    print json.dumps(topo)
    with open('topo%s.json' % str(n), 'w') as f:
        json.dump(topo, f, indent=2)
    nx.draw(G, with_labels=True)
    plt.savefig("topo%s.png" % str(n))
    plt.show()
    return
    result = {}

    for i in range(n):
        result[str(i) + '1'] = {'neighbor': []}
    for e in G.edges:
        result[str(e[0]) + '1']['neighbor'].append(str(e[1]) + '1')
        result[str(e[1]) + '1']['neighbor'].append(str(e[0]) + '1')

    print result
    with open('gentopo.out.json', 'w') as f:
        f.write(json.dumps(result))


gen_topo(3)


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
