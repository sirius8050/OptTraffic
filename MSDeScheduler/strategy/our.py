import os
import json
import random
import threading
import time
from fractions import Fraction
from typing import Dict, List, Tuple

from ..operation.HotExchange import operate
from ..metrics.TrafficGraph import Vertices, Graph, GraphSet, Edge
from ..metrics.ClusterStatus import NodeStatus, NodeStatusSet
from ..operation.TrafficAllocate import TrafficAllocate


class OurMethod:
    def __init__(self, graphSet: GraphSet, nodeSet: NodeStatusSet):
        self.graphSet = graphSet
        self.nodeSet = nodeSet
        self.Threshold = 4000
        self.serviceEdge: Dict[str: int] = {}
        # 记录哪些Service-Service链路已经被本地化
        self.graph_service: Dict[str, List[str]] = {}
        self.graph_service_service: Dict[str, Dict[str, bool]] = {}
        self.__OurMethodInit()
        # 待执行的exec
        self.exec_list = {}

    def __OurMethodInit(self):
        for graph in self.graphSet.GraphSet.keys():
            self.graph_service[graph] = []
            self.graph_service_service[graph] = {}
            topo = self.graphSet.GraphSet[graph].GraphTopology
            for i in topo.keys():
                if topo[i] is not None:
                    if isinstance(topo[i], str):
                        self.graph_service_service[graph][i + '~' + topo[i]] = False
                    else:
                        for j in topo[i]:
                            self.graph_service_service[graph][i + '~' + j] = False

    def choice_DAG(self):
        with open('/home/k8s/exper/zxz/MSScheduler_python/DAG/build/big_graph.json', 'r') as f:
            data = json.load(f)
        result = {}
        res = []
        for i in data['topo'].keys():
            if data['topo'][i] != '':
                for j in data["topo"][i]:
                    result['zxz-test~' + i + '~' + j] = data['meta'][i][1] + data['meta'][j][2]

        value = list(result.values())
        while True:
            a = max(value)
            if a < 4000:
                break
            value.remove(a)
            for i in result.keys():
                if result[i] == a:
                    res.append(i)
                    del result[i]
                    break
        return res


    def choiceEdges(self):
        # 找具有最大的流量的Service交互
        serviceEdge: Dict[str, int] = {}
        print('开始选择大流量边')
        # print(self.graphSet.GraphSet.keys())
        # print(self.graphSet.GraphSet['zxz-test'].EdgeSet.keys())
        for graph in self.graphSet.GraphSet.keys():
            for edge in self.graphSet.GraphSet[graph].EdgeSet.keys():
                if edge in serviceEdge.keys():
                    serviceEdge[graph + '~' + self.graphSet.GraphSet[graph].EdgeSet[edge].UM.ServiceName + '~'
                                + self.graphSet.GraphSet[graph].EdgeSet[edge].DM.ServiceName] \
                        += self.graphSet.GraphSet[graph].EdgeSet[edge].Send \
                           + self.graphSet.GraphSet[graph].EdgeSet[edge].Receive
                else:
                    serviceEdge[graph + '~' + self.graphSet.GraphSet[graph].EdgeSet[edge].UM.ServiceName + '~'
                                + self.graphSet.GraphSet[graph].EdgeSet[edge].DM.ServiceName] \
                        = self.graphSet.GraphSet[graph].EdgeSet[edge].Send \
                          + self.graphSet.GraphSet[graph].EdgeSet[edge].Receive
        self.serviceEdge = serviceEdge
        # print(serviceEdge)
        service: Dict[int, str] = {}
        for i in serviceEdge.keys():
            service[serviceEdge[i]] = i
        service_key = list(service.keys())
        service_key.sort(reverse=True)
        # print(serviceEdge)
        result = []
        # print(service_key)
        for i in service_key:
            # 若已经找到了一个service对流量已经低于Threshold还没有找到一个需要本地化的边，则退出
            if (service_key.index(i) + 1) / len(service_key) > 0.2:
                if len(result) == 0:
                    return False
                else:
                    # return result
                    break
            
            target = service[i]
            graph = target[:target.index('~')]
            target = target[target.index('~') + 1:]
            # 判断一对Service是否已经进行了本地化，若没有则进行本地化。若已经进行了本地化，则向后继续寻找边
            if not self.graph_service_service[graph][target]:
                # self.graph_service_service[graph][target] = True
                # 将进行了本地化的节点添加到graph—service中，对后续本地化移动步骤有影响
                # if graph in self.graph_service.keys():
                #     self.graph_service[graph].append(target[:target.index('~')])
                #     self.graph_service[graph].append(target[target.index('~') + 1:])
                # else:
                #     self.graph_service[graph] = [target[:target.index('~')], target[target.index('~') + 1:]]
                result.append(graph + '~' + target)
                
        res = self.choice_DAG()
        print('our result is:', res)       
        self.graphSet.serviceEdge = res
        return res

    def Localize_i(self, result: str):
        """
        本函数用于将指定的Service-Service对进行本地化。
        中间一共需要考虑三种情况：
            1v1：此情况下只需要将这对容器放一起
            1vn：能将几个放一起就将几个放一起，可以同时考虑所有的链路，拟合速度比NetMARKS以边为单位拟合更快
            nvn：尽量去保证每台节点内上下游副本比例和整个集群内上下游比例接近。
        :return:
        """

        # TODO:迁移过程中，可能上游微服务或者下游微服务已经进行了本地化，如果还拉它来进行本地化
        #  应优先保证他们是不动的
        def update(result):
            graph, um, dm = result.split('~')
            self.graph_service_service[graph][um + '~' + dm] = True
            if graph in self.graph_service.keys():
                if um not in self.graph_service[graph]:
                    self.graph_service[graph].append(um)
                if dm not in self.graph_service[graph]:
                    self.graph_service[graph].append(dm)

        # 获得需要LocalFirst的service对
        # result = self.choiceEdges()
        # result = 'social-network~user-mention-service~text-service'
        graph, um, dm = result.split('~')
        # TA初始化
        # TA = TrafficAllocate(self.graphSet.GraphSet[graph])
        um_list, dm_list = [], []
        # print(self.graphSet.GraphSet[graph].VerticesSet.keys())
        if None in self.graphSet.GraphSet[graph].VerticesSet.keys():
            del self.graphSet.GraphSet[graph].VerticesSet[None]
        for i in self.graphSet.GraphSet[graph].VerticesSet.keys():
            if um == i[:len(um)] and i[len(um)] == '-':
                um_list.append(self.graphSet.GraphSet[graph].VerticesSet[i])
            if dm == i[:len(dm)] and i[len(dm)] == '-':
                dm_list.append(self.graphSet.GraphSet[graph].VerticesSet[i])

        hotExchange = operate(self.graphSet, self.graphSet.GraphSet[graph], self.nodeSet)

        # 得到choice之后就需要将所有上下游的Pod从Freedom到Matched
        if isinstance(self.graphSet.GraphSet[graph].GraphTopology[um], List):
            if dm in self.graphSet.GraphSet[graph].GraphTopology[um]:
                pass
            else:
                um, dm = dm, um
        else:
            if dm == self.graphSet.GraphSet[graph].GraphTopology[um]:
                pass
            else:
                um, dm = dm, um
        for node in self.nodeSet.NodeNameSet:
            self.nodeSet.NodeSet[node].MatchedPod[um + '~' + dm] = ([], [])
            for pod in self.nodeSet.NodeSet[node].FreedomPod:
                if pod.ServiceName == um:
                    self.nodeSet.NodeSet[node].FreedomPod.remove(pod)
                    self.nodeSet.NodeSet[node].MatchedPod[um + '~' + dm][0].append(pod)
                if pod.ServiceName == dm:
                    self.nodeSet.NodeSet[node].FreedomPod.remove(pod)
                    self.nodeSet.NodeSet[node].MatchedPod[um + '~' + dm][1].append(pod)

        # update(result)
        # 1v1
        # 若双方都只有一个容器，且在同一台机器上，或者双方都是Stateful，则跳过处理，直接标记为已经本地化了
        if len(um_list) == 1 and len(dm_list) == 1:
            print('1v1类型')
            update(result)
            if (um_list[0].NodeName == dm_list[0].NodeName) \
                    or (um_list[0].Stateful and dm_list[0].Stateful) \
                    or (um_list[0].ServiceName not in self.graph_service[graph]
                        and dm_list[0].ServiceName not in self.graph_service[graph]):
                update(result)
            elif um_list[0].Stateful or dm_list[0].Stateful:
                if um_list[0].Stateful or um_list[0].ServiceName not in self.graph_service[graph]:
                    update(result)
                    hotExchange.HotExchange(self.graph_service, self.graphSet.GraphSet[graph].VerticesSet[dm_list[0].Name], um,
                                            um_list[0].NodeName,
                                            self.serviceEdge[result] / sum(list(self.serviceEdge.values())), self.exec_list)
                    # start = threading.Thread(target=hotExchange.HotExchange,
                    #                          args=(dm_list[0].Name, um, um_list[0].NodeName,
                    #                                self.serviceEdge[result] / sum(list(self.serviceEdge.values()))))
                    # start.start()
                    # start.join()
                    # TA.ExecuteNode(um + '~' + dm)
                elif dm_list[0].Stateful or dm_list[0].ServiceName not in self.graph_service[graph]:
                    update(result)
                    hotExchange.HotExchange(self.graph_service, self.graphSet.GraphSet[graph].VerticesSet[um_list[0].Name], dm,
                                            dm_list[0].NodeName,
                                            self.serviceEdge[result] / sum(list(self.serviceEdge.values())), self.exec_list)
            elif not um_list[0].Stateful and not dm_list[0].Stateful:
                if random.random() > 0.5:
                    update(result)
                    hotExchange.HotExchange(self.graph_service, self.graphSet.GraphSet[graph].VerticesSet[dm_list[0].Name], um,
                                            um_list[0].NodeName,
                                            self.serviceEdge[result] / sum(list(self.serviceEdge.values())), self.exec_list)
                    # TA.ExecuteNode(um + '~' + dm)
                else:
                    update(result)
                    hotExchange.HotExchange(self.graph_service, self.graphSet.GraphSet[graph].VerticesSet[um_list[0].Name], dm,
                                            dm_list[0].NodeName,
                                            self.serviceEdge[result] / sum(list(self.serviceEdge.values())), self.exec_list)
                    # TA.ExecuteNode(um + '~' + dm)
            update(result)
            return True

        # 1vn
        # 首先判断两个数组的长度是否是1vn or nv1类型。
        if (len(dm_list) == 1 and len(um_list) > 1) or (len(dm_list) > 1 and len(um_list) == 1):
            print('1vn or nv1 类型')
            # 设置solo list为长度为1的列表，more list 为长度大于1的列表
            if len(dm_list) == 1:
                solo_list = dm_list
                more_list = um_list
            else:
                solo_list = um_list
                more_list = dm_list

            # 两个都为Stateful无法进行hotExchange
            if more_list[0].Stateful and solo_list[0].Stateful:
                update(result)
                return False
            # 判断两个service是否之前已经参与过本地化。若都没参加过，或者只有solo参加过，或则solo是stateful
            if more_list[0].ServiceName not in self.graph_service[graph] and not more_list[0].Stateful:
                service_service = more_list[0].ServiceName + '~' + solo_list[0].ServiceName
                if service_service not in self.graph_service_service[graph].keys():
                    service_service = solo_list[0].ServiceName + '~' + more_list[0].ServiceName
                update(result)
                for pod in more_list:
                    if pod.NodeName != solo_list[0].NodeName:
                        hotExchange.HotExchange(self.graph_service, pod, solo_list[0].ServiceName, solo_list[0].NodeName,
                                                self.serviceEdge[result] / sum(list(self.serviceEdge.values())), self.exec_list)
                        # TA.ExecuteNode(um + '~' + dm)
            # more参加过本地化，solo.sh 没有
            elif not solo_list[0].Stateful and solo_list[0].ServiceName not in self.graph_service[graph]:
                update(result)
                for pod in more_list:
                    if pod.NodeName != solo_list[0].NodeName:
                        hotExchange.HotExchange(self.graph_service, pod, pod.ServiceName, pod.NodeName,
                                                self.serviceEdge[result] / sum(list(self.serviceEdge.values())), self.exec_list)
                        # TA.ExecuteNode(um + '~' + dm)
                        break
            update(result)
            return True

        # nvn 若为nvn格式，则二者都是Stateless
        # 获得外部比例，其为约分之后的值
        if len(um_list) > 1 and len(dm_list) > 1:
            # print('\n', self.graph_service[graph])
            # print(um_list[0].ServiceName, )
            if um_list[0].ServiceName in self.graph_service[graph] \
                    and dm_list[0].ServiceName in self.graph_service[graph]:
                return False
            print('nvn')
            external_ratio = Fraction(len(um_list), len(dm_list))
            # 记录每个node上有哪些上下游pod
            node_vertice: Dict[str, List[List[Vertices], List[Vertices]]] = {}
            # 记录每个机器上上下游pod的个数
            node_ratio: Dict[str, List[int, int]] = {}

            for i in self.nodeSet.NodeNameSet:
                node_vertice[i] = [[], []]
            for i in um_list:
                if i.NodeName in node_vertice.keys():
                    node_vertice[i.NodeName][0].append(i)
                else:
                    node_vertice[i.NodeName][0] = [i]
            for i in dm_list:
                if i.NodeName in node_vertice.keys():
                    node_vertice[i.NodeName][1].append(i)
                else:
                    node_vertice[i.NodeName][1] = [i]

            # 得到全部内部比例
            for i in node_vertice.keys():
                node_ratio[i] = [len(node_vertice[i][0]), len(node_vertice[i][1])]

            # 操作列表，用于记录所有移动操作，后续用于实现
            operate_list = [[], []]

            # 先将外部比例中分子或分母叫较小的一方先进行处理。处理方式为判断增减几个会给组内比例最接近组外比例
            # 当处理完其中一方后，再处理另一方，这样可以使获得移动次数最少。
            low = [external_ratio.numerator, external_ratio.denominator]

            flag = 0
            if um_list[0].ServiceName in self.graph_service[graph]:
                # 意味着此时UM已经进行过了本地化
                flag = 1
            elif dm_list[0].ServiceName in self.graph_service[graph]:
                # 意味着DM已经进行过了本地化
                flag = 2
            low = low.index(min(low))
            high = 1 - low
            # print('flag=', flag, '    low=', low)
            if flag == 0 or (flag == 1 and low == 1) or (flag == 2 and low == 0):
                # 每个机器生成的数量；每个机器需要消耗的数量
                produce: Dict[str, int] = {}
                consumer: Dict[str, int] = {}
                for i in node_ratio.keys():
                    if node_ratio[i][1] == 0:
                        fraction = 10000000
                    else:
                        fraction = Fraction(node_ratio[i][0], node_ratio[i][1])
                    if fraction != external_ratio:
                        if node_ratio[i][1 - low] * external_ratio ** (1 - 2 * low) > node_ratio[i][low]:
                            consumer[i] = round(
                                node_ratio[i][1 - low] * external_ratio ** (1 - 2 * low) - node_ratio[i][low])
                        elif node_ratio[i][1 - low] * external_ratio ** (1 - 2 * low) < node_ratio[i][low]:
                            produce[i] = round(
                                -node_ratio[i][1 - low] * external_ratio ** (1 - 2 * low) + node_ratio[i][low])
                # print(node_ratio)
                # print('consumer, produce  ', consumer, produce)

                a, b = 0, 0
                consumer_key, product_key = list(consumer.keys()), list(produce.keys())
                while True:
                    if a == len(consumer.keys()) or len(produce.keys()) == b:
                        break
                    i, j = consumer_key[a], product_key[b]
                    if consumer[i] > produce[j]:
                        consumer[i] = consumer[i] - produce[j]
                        node_ratio[i][low] += produce[j]
                        node_ratio[j][low] -= produce[j]
                        if produce[j] > 0:
                            operate_list[low].append(j + '~' + i + ':' + str(produce[j]))
                        b += 1
                        continue
                    else:
                        produce[j] = produce[j] - consumer[i]
                        node_ratio[i][low] += consumer[i]
                        node_ratio[j][low] -= consumer[i]
                        if consumer[i] > 0:
                            operate_list[low].append(j + '~' + i + ':' + str(consumer[i]))
                        a += 1
                        continue

            # print('flag=', flag, '    low=', low)
            # 分子分母较小的一方已经处理完毕，现在处理分子分母较大的一方
            if flag == 0 or (flag == 1 and low == 0) or (flag == 2 and low == 1):
                produce: Dict[str, int] = {}
                consumer: Dict[str, int] = {}
                for i in node_ratio.keys():
                    if node_ratio[i][1] == 0:
                        fraction = 10000000
                    else:
                        fraction = Fraction(node_ratio[i][0], node_ratio[i][1])
                    if fraction != external_ratio:
                        if node_ratio[i][low] / external_ratio ** (1 - 2 * low) > node_ratio[i][high]:
                            consumer[i] = round(
                                node_ratio[i][low] / external_ratio ** (1 - 2 * low) - node_ratio[i][high])
                        elif node_ratio[i][low] / external_ratio ** (1 - 2 * low) < node_ratio[i][high]:
                            produce[i] = round(
                                -node_ratio[i][low] / external_ratio ** (1 - 2 * low) + node_ratio[i][high])

                # print(node_ratio)
                # print('consumer, produce  ', consumer, produce)
                # consumer来消耗produce
                a, b = 0, 0
                consumer_key, product_key = list(consumer.keys()), list(produce.keys())
                while True:
                    if a == len(consumer.keys()) or len(produce.keys()) == b:
                        break
                    i, j = consumer_key[a], product_key[b]
                    if consumer[i] > produce[j]:
                        consumer[i] = consumer[i] - produce[j]
                        node_ratio[i][high] += produce[j]
                        node_ratio[j][high] -= produce[j]
                        if produce[j] > 0:
                            operate_list[high].append(j + '~' + i + ':' + str(produce[j]))
                        b += 1
                        continue
                    else:
                        produce[j] = produce[j] - consumer[i]
                        node_ratio[i][high] += consumer[i]
                        node_ratio[j][high] -= consumer[i]
                        if consumer[i] > 0:
                            operate_list[high].append(j + '~' + i + ':' + str(consumer[i]))
                        a += 1
                        continue

            # print(operate_list)
            # 将操作列表中操作实现
            node_um: Dict[str, List[Vertices]] = {'skv-node2':[], 'skv-node3':[], 'skv-node4':[], 'skv-node6':[], 'skv-node7':[]}
            node_dm: Dict[str, List[Vertices]] = {'skv-node2':[], 'skv-node3':[], 'skv-node4':[], 'skv-node6':[], 'skv-node7':[]}
            for i in um_list:
                if i.NodeName not in node_um.keys():
                    node_um[i.NodeName] = [i]
                else:
                    node_um[i.NodeName].append(i)
            for i in dm_list:
                if i.NodeName not in node_dm.keys():
                    node_dm[i.NodeName] = [i]
                else:
                    node_dm[i.NodeName].append(i)

            # print(node_um, node_dm)
            # print(operate_list)
            # print(node_um,'   ', node_dm)
            hotExchangePoll = []
            for i in range(len(operate_list[0])):
                op = operate_list[0][i]
                source_node, target_node, num = \
                    op[:op.index('~')], op[op.index('~') + 1: op.index(':')], int(op[op.index(':') + 1])
                for j in range(num):
                    update(result)
                    # print('OP', op, 'node_um', node_um)
                    # print(self.graphSet.GraphSet[node_um[source_node][j].MSName].VerticesSet.keys())
                    try:
                        hotExchange.HotExchange(self.graph_service, self.graphSet.GraphSet[node_um[source_node][j].MSName].VerticesSet[
                                                    node_um[source_node][j].Name],
                                                dm, target_node,
                                                # 计算当前service的流量占整个应用所有service流量的比例
                                                self.serviceEdge[result] / max(sum(list(self.serviceEdge.values())), 0.1), self.exec_list)
                        # # 去除node_um中的被迁移的Pod
                        node_um[source_node][j] = 'del'
                    except:
                        # print(self.serviceEdge.keys())
                        time.sleep(4)
                        hotExchange.HotExchange(self.graph_service, self.graphSet.GraphSet[node_um[source_node][j].MSName].VerticesSet[
                                                    node_um[source_node][j].Name],
                                                dm, target_node,
                                                self.serviceEdge[result] / sum(list(self.serviceEdge.values())), self.exec_list)
                        node_um[source_node][j] = 'del'
                # 清空node中需要迁移的um，因为已经全部迁移完毕
                length = len(node_um[source_node])
                for i in range(length):
                    if node_um[source_node][length - 1 - i] == 'del':
                        del node_um[source_node][length - 1 - i]
                    # hotExchangePoll.append(threading.Thread(
                    #     target=hotExchange.HotExchange,
                    #     args=(node_um[source_node][j].Name,
                    #           dm, target_node, self.serviceEdge[result] / sum(list(self.serviceEdge.values())))))
            for i in range(len(operate_list[1])):
                op = operate_list[1][i]
                source_node, target_node, num = \
                    op[:op.index('~')], op[op.index('~') + 1: op.index(':')], int(op[op.index(':') + 1])
                for j in range(num):
                    update(result)
                    try:
                        hotExchange.HotExchange(self.graph_service, self.graphSet.GraphSet[node_dm[source_node][j].MSName].VerticesSet[
                                                node_dm[source_node][j].Name],
                                            um, target_node,
                                            self.serviceEdge[result] / sum(list(self.serviceEdge.values())), self.exec_list)
                    except:
                        time.sleep(4)
                        hotExchange.HotExchange(self.graph_service, self.graphSet.GraphSet[node_um[source_node][j].MSName].VerticesSet[
                                                    node_um[source_node][j].Name],
                                                dm, target_node,
                                                self.serviceEdge[result] / sum(list(self.serviceEdge.values())), self.exec_list)
                    # hotExchangePoll.append(threading.Thread(
                    #     target=hotExchange.HotExchange,
                    #     args=(node_dm[source_node][j].Name,
                    #           um, target_node, self.serviceEdge[result] / sum(list(self.serviceEdge.values())))))
            # for i in hotExchangePoll:
            #     i.start()
            # for i in hotExchangePoll:
            #     i.join()
            # TA.ExecuteNode(um + '~' + dm)
            update(result)
            return True
        
        update(result)
        return False

    def Localize(self):
        result = self.choiceEdges()
        # result = self.choice_DAG()
        
        # result = ['social-network~text-service~user-mention-service']
        self.graphSet.serviceEdge = result
        # result = ['social-network~user-timeline-service~user-timeline-mongodb', 'social-network~user-mention-service~user-memcached', 'social-network~home-timeline-service~home-timeline-redis', 'social-network~post-storage-service~post-storage-mongodb', 'social-network~url-shorten-service~url-shorten-mongodb', 'social-network~social-graph-service~social-graph-redis', 'social-network~user-service~user-mongodb', 'social-network~text-service~user-mention-service', 'social-network~home-timeline-service~post-storage-service', 'social-network~user-timeline-service~user-timeline-redis', 'social-network~compose-post-service~text-service', 'social-network~nginx-thrift~compose-post-service', 'social-network~compose-post-service~post-storage-service', 'social-network~home-timeline-service~social-graph-service', 'social-network~text-service~url-shorten-service', 'social-network~compose-post-service~user-service', 'social-network~compose-post-service~media-service.json', 'social-network~compose-post-service~user-timeline-service', 'social-network~compose-post-service~home-timeline-service', 'social-network~compose-post-service~unique-id-service']

        # return
        if not result:
            return False
        for i in result:
            print('now is :', i)
            self.Localize_i(i)
            time.sleep(1)
            # print(self.exec_list)
        for thr in self.exec_list.keys():
            self.exec_list[thr].start()
        for thr in self.exec_list.keys():
            self.exec_list[thr].join(600)
            
        self.exec_list = []

        print("开始TA")
        print(self.graphSet.GraphSet['zxz-test'].VerticesSet.keys())
        while True:
            ter = ''.join(os.popen('kubectl get pod -n zxz-test -o wide | grep Terminating'))
            if ter == '':
                break
            time.sleep(2)
        
        for i in result:
            graph, link = i[:i.index('~')], i[i.index('~') + 1:]
            TA = TrafficAllocate(self.graphSet.GraphSet[graph])
            TA.ExecuteNode(link)

        return True

    def TA(self, result):
        # result = self.choiceEdges()
        # result = ['social-network~nginx-thrift~home-timeline-service',
        #           'social-network~home-timeline-service~post-storage-service']
        self.graphSet.serviceEdge = result
        # result = ['social-network~user-timeline-service~user-timeline-mongodb', 'social-network~user-mention-service~user-memcached', 'social-network~home-timeline-service~home-timeline-redis', 'social-network~post-storage-service~post-storage-mongodb', 'social-network~url-shorten-service~url-shorten-mongodb', 'social-network~social-graph-service~social-graph-redis', 'social-network~user-service~user-mongodb', 'social-network~text-service~user-mention-service', 'social-network~home-timeline-service~post-storage-service', 'social-network~user-timeline-service~user-timeline-redis', 'social-network~compose-post-service~text-service', 'social-network~nginx-thrift~compose-post-service', 'social-network~compose-post-service~post-storage-service', 'social-network~home-timeline-service~social-graph-service', 'social-network~text-service~url-shorten-service', 'social-network~compose-post-service~user-service', 'social-network~compose-post-service~media-service.json', 'social-network~compose-post-service~user-timeline-service', 'social-network~compose-post-service~home-timeline-service', 'social-network~compose-post-service~unique-id-service']
        ta_exec = []
        if not result:
            return False
        # print(result)
        for i in result:
            # self.Localize_i(i)
            time.sleep(1)
            # for j in self.graphSet.GraphSet['social-network'].VerticesSet.keys():
            #     print(self.graphSet.GraphSet['social-network'].VerticesSet[j].Name, ':', self.graphSet.GraphSet['social-network'].VerticesSet[j].NodeName)
        TA = TrafficAllocate(self.graphSet.GraphSet[graph])
        for graph in self.graphSet.GraphSet.keys():
            for um in self.graphSet.GraphSet[graph].GraphTopology.keys():
                if isinstance(self.graphSet.GraphSet[graph].GraphTopology[um], str):
                    if self.graphSet.GraphSet[graph].GraphTopology[um] != '':
                        link = um + '~' + self.graphSet.GraphSet[graph].GraphTopology[um]
                        
                        # print(link)
                        ta_exec.append(threading.Thread(target=TA.ExecuteNode, args=(link)))
                        
                elif isinstance(self.graphSet.GraphSet[graph].GraphTopology[um], list):
                    for dm in self.graphSet.GraphSet[graph].GraphTopology[um]:
                        link = um + '~' + dm
                        # TA = TrafficAllocate(self.graphSet.GraphSet[graph])
                        # print(link)
                        ta_exec.append(threading.Thread(target=TA.ExecuteNode, args=(link)))

        for i in result:
            graph, link = i[:i.index('~')], i[i.index('~') + 1:]
            # TA = TrafficAllocate(self.graphSet.GraphSet[graph])
            ta_exec.append(threading.Thread(target=TA.ExecuteNode, args=(link)))
        
        for i in ta_exec:
            i.start()
            i.join()
        return True