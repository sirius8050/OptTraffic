import os
import sys
import threading
import time

from MSDeScheduler.metrics.ClusterStatus import NodeStatusSet
from MSDeScheduler.metrics.GetTrafficGraph import InitTrafficGraphSet, graphFlash, CheckRing, LineEquationSolution
from MSDeScheduler.strategy.our import OurMethod
from MSDeScheduler.strategy.baseline import LocalizeHeavyTraffic
# from MSDeScheduler.strategy.localfirst import LocalizeHeavyTraffic
from MSDeScheduler.operation.TrafficAllocate import TrafficAllocate


def main(argv):
    # graphSet相关
    graphSet = InitTrafficGraphSet()
    for graph in graphSet.GraphSet.keys():
        graphFlash(graphSet.GraphSet[graph])
    # nodeSet相关
    nodeSet = NodeStatusSet()
    nodeSet.DataStructInit(graphSet)

    while True:
        for graph in graphSet.GraphSet.keys():
            graphFlash(graphSet.GraphSet[graph])
            # print(graphSet.GraphSet[graph].GraphTopology)
            CheckRing(graphSet.GraphSet[graph])
            LineEquationSolution(graphSet.GraphSet[graph])

        baseline = LocalizeHeavyTraffic(graphSet, nodeSet)
        our = OurMethod(graphSet, nodeSet)


        # for a in graphSet.GraphSet.keys():
        #     for v in graphSet.GraphSet[a].VerticesSet.keys():
        #         print(v, '     stateful:', graphSet.GraphSet[a].VerticesSet[v].Stateful)

        if argv[1] == 'baseline':
            use = baseline
            print(use.OptimumLocalize())
        elif argv[1] == 'our':
            use = our
            print(use.Localize())
        elif argv[1] == 'restrict':
            use = baseline
            print('baseline')
            # print(use.RestrictLocalize())
            use.Localize_bigDAG_samenode()
        elif argv[1] == 'TA':
            use = our
            use.TA()
        break


if __name__ == '__main__':
    main(sys.argv)


