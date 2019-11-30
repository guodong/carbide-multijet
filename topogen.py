#!/usr/bin/env python2

import sys
import math
import networkx as nx
import matplotlib.pyplot as plt
import argparse
import json


def main():
    parser = argparse.ArgumentParser(description="Topology configuration file generator")
    parser.add_argument("source", type=str, help="GraphML file")
    parser.add_argument("--output","-o", type=str, default=None, help="Output JSON file")

    args = parser.parse_args()
    outputfile = args.output
    topo = nx.read_graphml(args.source).to_undirected()

    index = 100
    labels = {}
    for n in topo.adj:
        labels[n] = str(index)
        index += 1
    # pos = nx.spring_layout(topo)
    pos = nx.fruchterman_reingold_layout(topo, center=(0, 0))

    nx.draw(topo, pos=pos)
    nx.draw_networkx_labels(topo, pos, labels=labels)
    plt.savefig(outputfile + '-topo.png')
    # plt.show()
    # return

    switches = {labels[n] : {'neighbor': []} for n in topo.adj}

    links = set()
    for link, attr in topo.edges.items():
        # id = attr['id']
        print(attr)
        pair = labels[link[0]], labels[link[1]]
        # assert pair not in links
        links.add(pair)
        links.add((pair[1], pair[0]))

    for a,b in links:
        assert b not in switches[a]['neighbor']
        switches[a]['neighbor'].append(b)

    print("switch len", len(switches))
    print("links len", len(links))

    if outputfile:
        fp = open(outputfile, 'w')
    else:
        fp = sys.stdout

    json.dump(switches, fp, indent=2)


if __name__ == "__main__":
    main()