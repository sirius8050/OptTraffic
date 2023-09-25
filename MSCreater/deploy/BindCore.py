import os
import sys
import json


def map_init():
    node = ['skv-node2', 'skv-node3', 'skv-node4', 'skv-node6', 'skv-node7']
    core = 80
    node_map = {}
    for node_i in node:
        node_map[node_i] = {}
        for i in range(core):
            node_map[node_i][i] = []
    f = open('./MSCreater/yaml_read/node_map.json', 'w')
    json.dump(node_map, f)
    f.close()


def main(argv):
    f = open('./MSCreater/yaml_read/node_map.json', 'r')
    data = json.load(f)
    f.close()
    type = argv[1]
    node = argv[2]
    core = argv[3]
    service = None
    if type == 'add':
        service = argv[4]
    if type == 'add':
        for core_i in core.split(','):
            data[node][core_i].append(service)
    elif type == 'del':
        for core_i in core.split(','):
            data[node][core_i].remove(service)
            
    f = open('./MSCreater/yaml_read/node_map.json', 'w')
    json.dump(data, f)
    f.close()


if __name__ == '__main__':
    # map_init()
    main(sys.argv)


