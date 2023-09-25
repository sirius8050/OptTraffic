import sys
import json
import copy


def GetTopology(ServiceName, path):
    TopologyPath = path + ServiceName
    Topology = open(TopologyPath, 'r')
    topo = json.load(Topology)
    Topology.close()

    data = topo[list(topo.keys())[0]]
    name = list(data.keys())
    for i in name:
        if isinstance(data[i], str):
            if data[i] not in data.keys():
                data[data[i]] = ''
        elif isinstance(data[i], list):
            for j in data[i]:
                if j not in data.keys():
                    data[j] = ''
        else:
            raise TypeError('Topology is not correct.')
    return topo
