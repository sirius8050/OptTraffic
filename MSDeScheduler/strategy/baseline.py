import os
import random
import json
from time import time
from unittest import result
import requests
from typing import Dict, List, Tuple
from MSDeScheduler.operation.HotExchange import operate
from MSDeScheduler.metrics.TrafficGraph import Vertices, Graph, GraphSet, Edge
from MSDeScheduler.metrics.ClusterStatus import NodeStatus, NodeStatusSet


def get_node_cpu_spend(node):
    result = []
    for node_i in node:
        data = ''.join(os.popen(f"kubectl describe node {node_i} | grep cpu | grep %"))
        per = data[data.index('(')+1:data.index('%')]
        result.append(int(per))
    return result[0], result[1]


class LocalizeHeavyTraffic:

    def __init__(self, graphSet: GraphSet, nodeSet: NodeStatusSet):
        self.graphSet = graphSet
        self.nodeSet = nodeSet
        self.result: List[Edge] = []
        self.translated = []
        self.translatedMap = {}
        # 当跨节点流量小于Threshold时不进行流量本地化
        self.Threshold = 10000
        self.exec_list = []

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
            if a < 20000:
                break
            value.remove(a)
            for i in result.keys():
                if result[i] == a:
                    res.append(i)
                    del result[i]
                    break
        return res

    def choiceEdge_fake(self):
        res = self.choice_DAG()
        # # 先找到有最大的跨节点流量的链路。
        flag = 1
        print(res)
        for i in res:
            graph, um, dm = i.split('~')
            um_pod_node = {}
            dm_pod_node = {}
            for j in self.graphSet.GraphSet[graph].ServiceSet[um]:
                um_pod_node[j.Name] = j.NodeName
            for j in self.graphSet.GraphSet[graph].ServiceSet[dm]:
                dm_pod_node[j.Name] = j.NodeName

            for j in um_pod_node.copy().keys():
                for k in dm_pod_node.copy().keys():
                    if um_pod_node[j] == dm_pod_node[k]:
                        del um_pod_node[j]
                        del dm_pod_node[k]
                        break
            print(um_pod_node, dm_pod_node)
            for j in range(len(list(um_pod_node.copy().keys()))):
                self.result.append(self.graphSet.GraphSet[graph].EdgeSet[list(um_pod_node.keys())[j]+'~'+list(dm_pod_node.keys())[j]])
        
        if flag:
            return True
        else:
            return False
    
    def choiceEdge_bigDAG(self):
        res = self.choice_DAG()
        # # 先找到有最大的跨节点流量的链路。
        flag = 1
        print(res)
        for i in res:
            graph, um, dm = i.split('~')
            um_pod_node = {}
            dm_pod_node = {}
            for j in self.graphSet.GraphSet[graph].ServiceSet[um]:
                um_pod_node[j.Name] = j.NodeName
            for j in self.graphSet.GraphSet[graph].ServiceSet[dm]:
                dm_pod_node[j.Name] = j.NodeName

            # process
            node1, node2 = '', ''
            for j in list(um_pod_node.keys()).extend(list(dm_pod_node.keys())):
                if node1 == '':
                    node1 = j
                else:
                    if j != node1:
                        node2 = j
            if node2 == '':
                continue
            else:
                pass
            for j in range(len(list(um_pod_node.copy().keys()))):
                self.result.append(self.graphSet.GraphSet[graph].EdgeSet[list(um_pod_node.keys())[j]+'~'+list(dm_pod_node.keys())[j]])
        if flag:
            return True
        else:
            return False

    def choiceEdge(self):
        # res = self.choice_DAG()
        # 先找到有最大的跨节点流量的链路。
        flag = 0
        trafficEdge: Dict[float, Tuple[Graph, Edge]] = {}
        for graph in self.graphSet.GraphSet.keys():
            for edge in self.graphSet.GraphSet[graph].EdgeSet.keys():
                traffic = self.graphSet.GraphSet[graph].EdgeSet[edge].Send \
                          + self.graphSet.GraphSet[graph].EdgeSet[edge].Receive
                trafficEdge[traffic + random.random()] = (self.graphSet.GraphSet[graph],
                                                          self.graphSet.GraphSet[graph].EdgeSet[edge])
            trafficEdge_key = list(trafficEdge.keys())
            trafficEdge_key.sort(reverse=True)
            # print(trafficEdge_key)
            # result = []
            for i in trafficEdge_key:
                # 如果不在一个机器上
                # if trafficEdge[i][1].UM.NodeName != trafficEdge[i][1].DM.NodeName:
                # 如果流量超过了Threshold
                # if i > self.Threshold:
                if (trafficEdge_key.index(i) + 1) / len(trafficEdge_key) < 0.2:
                    self.result.append(trafficEdge[i][1])
                    flag = 1
        if flag:
            return True
        else:
            return False

    '''
    def choiceEdge(self):
        result = ['nginx-thrift~home-timeline-service', 'home-timeline-service~post-storage-service']
        
    '''


    def Localize(self):
        self.translated = []
        # 无需进行流量本地化，返回False
        print('这是Localization')
        if not self.choiceEdge_fake():
            return False
        for i in self.result:
            print(i.UM.MSName + ': ' + i.Name)

        def trans_able(link: Edge, type: int) -> bool:
            if random.random() < 0.2:
                return False
            if link.DM.NodeName == link.UM.NodeName:
                self.translated.append(link.UM.MSName + '~' + link.UM.Name)
                self.translated.append(link.DM.MSName + '~' + link.DM.Name)
                return False

            deploy_UM, deploy_DM = '', ''
            flag = 0
            for i in range(1, len(link.UM.Name)):
                if link.UM.Name[-i] == '-':
                    flag += 1
                    if flag == 2:
                        deploy_UM = link.UM.Name[:-i]
                        break
            flag = 0
            for i in range(1, len(link.DM.Name)):
                if link.DM.Name[-i] == '-':
                    flag += 1
                    if flag == 2:
                        deploy_DM = link.DM.Name[:-i]
                        break

            if type == 0:
                if link.UM.MSName + '~' + deploy_UM in self.translated:
                    return False
                else:
                    self.translated.append(link.UM.MSName + '~' + deploy_UM)
                    return True
            elif type == 1:
                if link.DM.MSName + '~' + deploy_DM in self.translated:
                    return False
                else:
                    self.translated.append(link.DM.MSName + '~' + deploy_DM)
                    return True

        # for graph in self.targetGraphEdge.keys():
        # hotExchange = operate(self.graphSet,, self.nodeSet)
        for i in self.result:
            print('now is', i.Name)
            hotExchange = operate(self.graphSet, self.graphSet.GraphSet[i.UM.MSName], self.nodeSet)
            if i.DM.Stateful:
                print(i.UM.Name, i.DM.NodeName)
                if trans_able(i, 0):
                    hotExchange.HotTrans(i.UM, i.DM.NodeName, self.exec_list)
            elif i.UM.Stateful:
                print(i.DM.Name, i.UM.NodeName)
                if trans_able(i, 1):
                    hotExchange.HotTrans(i.DM, i.UM.NodeName, self.exec_list)
            else:
                if trans_able(i, 0):
                    print(i.UM.Name, i.DM.NodeName)
                    hotExchange.HotTrans(i.UM, i.DM.NodeName, self.exec_list)
                elif trans_able(i, 1):
                    print(i.DM.Name, i.UM.NodeName)
                    # if trans_able(i, 1):
                    hotExchange.HotTrans(i.DM, i.UM.NodeName, self.exec_list)
        # 流量本地化完成
        for i in self.exec_list:
            i.start()
        for i in self.exec_list:
            i.join(600)
        return True

    def OptimumLocalize(self):
        # 无需进行流量本地化，返回False
        if not self.choiceEdge():
            return False
        # self.result = ['social-network~nginx-thrift~home-timeline-service',
        #           'social-network~home-timeline-service~post-storage-service']
        for i in self.result:
            print(i.UM.MSName + ': ' + i.Name)

        def trans_able(link: Edge):
            print('现在是判断:', link.Name)
            hotExchange = operate(self.graphSet, self.graphSet.GraphSet[link.UM.MSName], self.nodeSet)
            # 第一次出现这对service
            if link.UM.MSName + '~' + link.UM.ServiceName + '~' + link.DM.ServiceName not in self.translatedMap.keys():
                # 在同一台机器上
                if link.DM.NodeName == link.UM.NodeName:
                    print('一样', link.DM.NodeName)
                    self.translatedMap[link.UM.MSName + '~' + link.UM.ServiceName + '~' + link.DM.ServiceName] \
                        = link.DM.NodeName
                    self.translated.append(link.UM.MSName + '~' + link.UM.ServiceName)
                    self.translated.append(link.DM.MSName + '~' + link.DM.ServiceName)
                    # return 0
                # 不在同一台机器上
                else:
                    # 需要判断其中一个是否已经出现在其他边中.
                    # 如果UM已经出现or stateful
                    if (link.UM.MSName + '~' + link.UM.ServiceName in self.translated or link.UM.Stateful) \
                            and not (link.DM.MSName + '~' + link.DM.ServiceName in self.translated or link.DM.Stateful):
                        self.translatedMap[link.UM.MSName + '~' + link.UM.ServiceName + '~' + link.DM.ServiceName] \
                            = link.UM.NodeName
                        self.translated.append(link.DM.MSName + '~' + link.DM.ServiceName)
                        hotExchange.HotTrans(link.DM, link.UM.NodeName, self.exec_list)

                    # 如果DM已经出现or stateful
                    elif not (link.UM.MSName + '~' + link.UM.ServiceName in self.translated or link.UM.Stateful) \
                            and (link.DM.MSName + '~' + link.DM.ServiceName in self.translated or link.DM.Stateful):
                        self.translatedMap[link.UM.MSName + '~' + link.UM.ServiceName + '~' + link.DM.ServiceName] \
                            = link.DM.NodeName
                        self.translated.append(link.UM.MSName + '~' + link.UM.ServiceName)
                        hotExchange.HotTrans(link.UM, link.DM.NodeName, self.exec_list)
                    # 如果都没有出现and not stateful
                    elif not (link.UM.MSName + '~' + link.UM.ServiceName in self.translated or link.UM.Stateful) \
                            and not (link.DM.MSName + '~' + link.DM.ServiceName in self.translated or link.DM.Stateful):
                        self.translatedMap[link.UM.MSName + '~' + link.UM.ServiceName + '~' + link.DM.ServiceName] \
                            = link.DM.NodeName
                        self.translated.append(link.UM.MSName + '~' + link.UM.ServiceName)
                        self.translated.append(link.UM.MSName + '~' + link.DM.ServiceName)
                        hotExchange.HotTrans(link.UM, link.DM.NodeName, self.exec_list)


            # 若不是第一次出现这对service
            if link.UM.MSName + '~' + link.UM.ServiceName + '~' + link.DM.ServiceName in self.translatedMap.keys():
                print(link.UM.NodeName, self.translatedMap[
                    link.UM.MSName + '~' + link.UM.ServiceName + '~' + link.DM.ServiceName])
                # 如果UM
                if link.UM.NodeName == self.translatedMap[
                    link.UM.MSName + '~' + link.UM.ServiceName + '~' + link.DM.ServiceName] and\
                        link.DM.NodeName == self.translatedMap[
                    link.UM.MSName + '~' + link.UM.ServiceName + '~' + link.DM.ServiceName]:
                    pass
                    # return 0
                elif link.DM.NodeName == self.translatedMap[
                    link.UM.MSName + '~' + link.UM.ServiceName + '~' + link.DM.ServiceName] and not link.UM.Stateful:
                    hotExchange.HotTrans(link.UM, link.DM.NodeName, self.exec_list)
                    # return 1
                elif link.UM.NodeName == self.translatedMap[
                    link.UM.MSName + '~' + link.UM.ServiceName + '~' + link.DM.ServiceName] and not link.DM.Stateful:
                    hotExchange.HotTrans(link.DM, link.UM.NodeName, self.exec_list)
                elif not link.UM.Stateful and not link.DM.Stateful:
                    hotExchange.HotTrans(link.UM, link.DM.NodeName, self.exec_list)
                    hotExchange.HotTrans(link.DM, link.UM.NodeName, self.exec_list)

        for i in self.result:
            trans_able(i)
        # 流量本地化完成
        return True

    def RestrictLocalize(self) -> bool:
        # TODO：修改此函数
        """
        此函数为带有限制条件的本地化函数。机器总资源是受限的。
        移动一个Pod之前会进行判断：如果目标机器内已经倍申请的资源超过了80%，则不进行移动
        :return: 是否成功执行
        """
        if not self.choiceEdge():
            return False
        for i in self.result:
            print(i.UM.MSName + ': ' + i.Name)

        def trans_able(link: Edge, type: int) -> bool:
            if link.DM.NodeName == link.UM.NodeName:
                self.translated.append(link.UM.MSName + '~' + link.UM.Name)
                self.translated.append(link.DM.MSName + '~' + link.DM.Name)
                return False

            deploy_UM, deploy_DM = '', ''
            flag = 0
            for i in range(1, len(link.UM.Name)):
                if link.UM.Name[-i] == '-':
                    flag += 1
                    if flag == 2:
                        deploy_UM = link.UM.Name[:-i]
                        break
            flag = 0
            for i in range(1, len(link.DM.Name)):
                if link.DM.Name[-i] == '-':
                    flag += 1
                    if flag == 2:
                        deploy_DM = link.DM.Name[:-i]
                        break

            if type == 0:
                if link.UM.MSName + '~' + deploy_UM in self.translated:
                    return False
                else:
                    self.translated.append(link.UM.MSName + '~' + deploy_UM)
                    return True
            elif type == 1:
                if link.DM.MSName + '~' + deploy_DM in self.translated:
                    return False
                else:
                    self.translated.append(link.DM.MSName + '~' + deploy_DM)
                    return True

        with open('/home/k8s/exper/zxz/MSScheduler_python/MSDeScheduler/strategy/percent.txt', 'r') as f:
            percent = int(f.read())
        # percent = 85

        for i in self.result:
            hotExchange = operate(self.graphSet, self.graphSet.GraphSet[i.UM.MSName], self.nodeSet, self.exec_list)
            # time.sleep(0.5)
            um_node, dm_node = get_node_cpu_spend([i.UM.NodeName, i.DM.NodeName])
            # print('信息：',um_node, dm_node)
            if um_node < percent and dm_node < percent:
                if i.DM.Stateful:
                    print(i.UM.Name, i.DM.NodeName)
                    if trans_able(i, 0):
                        hotExchange.HotTrans(i.UM, i.DM.NodeName, self.exec_list)
                elif i.UM.Stateful:
                    print(i.DM.Name, i.UM.NodeName)
                    if trans_able(i, 1):
                        hotExchange.HotTrans(i.DM, i.UM.NodeName, self.exec_list)
                else:
                    if trans_able(i, 0):
                        hotExchange.HotTrans(i.UM, i.DM.NodeName, self.exec_list)
                    elif trans_able(i, 1):
                        hotExchange.HotTrans(i.DM, i.UM.NodeName, self.exec_list)
            elif um_node < percent:
                if not i.DM.Stateful:
                    if trans_able(i, 1):
                        hotExchange.HotTrans(i.DM, i.UM.NodeName, self.exec_list)
            elif dm_node < percent:
                if not i.UM.Stateful:
                    if trans_able(i, 0):
                        hotExchange.HotTrans(i.UM, i.DM.NodeName, self.exec_list)
        # 流量本地化完成

        for i in self.exec_list:
            i.start()
        for i in self.exec_list:
            i.join()
        
        return True

    def Localize_bigDAG(self):
        res = self.choice_DAG()
        self.translated = []
        
        for link in res:
            graph, um, dm = link.split('~')
            um_pod_node = {}
            dm_pod_node = {}
            for j in self.graphSet.GraphSet[graph].ServiceSet[um]:
                um_pod_node[j.Name] = j.NodeName
            for j in self.graphSet.GraphSet[graph].ServiceSet[dm]:
                dm_pod_node[j.Name] = j.NodeName

            # process
            node1, node2 = '', ''
            # print(all_list)
            for j in um_pod_node.keys():
                if node1 == '':
                    node1 = um_pod_node[j]
                else:
                    if um_pod_node[j] != node1:
                        node2 = um_pod_node[j]
            for j in dm_pod_node.keys():
                if node1 == '':
                    node1 = dm_pod_node[j]
                else:
                    if dm_pod_node[j] != node1:
                        node2 = dm_pod_node[j]
            # print('node2', node2)
            if node2 == '':
                continue
            else:
                hotExchange = operate(self.graphSet, self.graphSet.GraphSet[graph], self.nodeSet)
                if um in self.translated and dm in self.translated:
                    continue
                elif um not in self.translated and dm in self.translated:
                    self.translated.append(um)
                    for j in self.graphSet.GraphSet[graph].ServiceSet[um]:
                        for k in dm_pod_node.keys():
                            # print(dm + '-' + j.Name[len(um) + 1], '      ', k)
                            if (dm + '-' + j.Name[len(um) + 1]) in k:
                                # print(um_pod_node.keys(), dm_pod_node.keys())
                                hotExchange.HotTrans(j, dm_pod_node[k], self.exec_list)
                                break
                elif dm not in self.translated and um in self.translated:
                    self.translated.append(dm)
                    for j in self.graphSet.GraphSet[graph].ServiceSet[dm]:
                        for k in um_pod_node.keys():
                            if (um + '-' + j.Name[len(dm) + 1]) in k:
                                hotExchange.HotTrans(j, um_pod_node[k], self.exec_list)
                                break
                else:
                    self.translated.append(um)
                    self.translated.append(dm)
                    um_list, dm_list = list(um_pod_node.keys()), list(dm_pod_node.keys())
                    
                    hotExchange.HotTrans(self.graphSet.GraphSet[graph].VerticesSet[um_list[0]], node1, self.exec_list)
                    hotExchange.HotTrans(self.graphSet.GraphSet[graph].VerticesSet[um_list[1]], node1, self.exec_list)
                    hotExchange.HotTrans(self.graphSet.GraphSet[graph].VerticesSet[um_list[2]], node2, self.exec_list)
                    hotExchange.HotTrans(self.graphSet.GraphSet[graph].VerticesSet[um_list[3]], node2, self.exec_list)

                    hotExchange.HotTrans(self.graphSet.GraphSet[graph].VerticesSet[dm_list[0]], node1, self.exec_list)
                    hotExchange.HotTrans(self.graphSet.GraphSet[graph].VerticesSet[dm_list[1]], node1, self.exec_list)
                    hotExchange.HotTrans(self.graphSet.GraphSet[graph].VerticesSet[dm_list[2]], node2, self.exec_list)
                    hotExchange.HotTrans(self.graphSet.GraphSet[graph].VerticesSet[dm_list[3]], node2, self.exec_list)

        for i in self.exec_list:
            i.start()
        for i in self.exec_list:
            i.join(600)
        return True


    def Localize_bigDAG_samenode(self):
        res = self.choice_DAG()
        print('baseline result is: ', res)
        res = res[:int(len(res) / 2)]
        self.translated = []
        
        for link in res:
            graph, um, dm = link.split('~')
            um_pod_node = {}
            dm_pod_node = {}
            for j in self.graphSet.GraphSet[graph].ServiceSet[um]:
                um_pod_node[j.Name] = j.NodeName
            for j in self.graphSet.GraphSet[graph].ServiceSet[dm]:
                dm_pod_node[j.Name] = j.NodeName

            # process
            node1, node2 = '', ''
            # print(all_list)
            for j in um_pod_node.keys():
                if node1 == '':
                    node1 = um_pod_node[j]
            for j in dm_pod_node.keys():
                if node2 == '':
                    node2 = dm_pod_node[j]

            hotExchange = operate(self.graphSet, self.graphSet.GraphSet[graph], self.nodeSet)
            um_list, dm_list = list(um_pod_node.keys()), list(dm_pod_node.keys())
            if um not in self.translated and dm not in self.translated:
                self.translated.append(um)
                self.translated.append(dm)

                hotExchange.HotTrans(self.graphSet.GraphSet[graph].VerticesSet[um_list[0]], node1, self.exec_list)
                hotExchange.HotTrans(self.graphSet.GraphSet[graph].VerticesSet[um_list[1]], node1, self.exec_list)
                hotExchange.HotTrans(self.graphSet.GraphSet[graph].VerticesSet[um_list[2]], node1, self.exec_list)
                hotExchange.HotTrans(self.graphSet.GraphSet[graph].VerticesSet[um_list[3]], node1, self.exec_list)

                hotExchange.HotTrans(self.graphSet.GraphSet[graph].VerticesSet[dm_list[0]], node1, self.exec_list)
                hotExchange.HotTrans(self.graphSet.GraphSet[graph].VerticesSet[dm_list[1]], node1, self.exec_list)
                hotExchange.HotTrans(self.graphSet.GraphSet[graph].VerticesSet[dm_list[2]], node1, self.exec_list)
                hotExchange.HotTrans(self.graphSet.GraphSet[graph].VerticesSet[dm_list[3]], node1, self.exec_list)
            elif um in self.translated:
                self.translated.append(um)

                hotExchange.HotTrans(self.graphSet.GraphSet[graph].VerticesSet[dm_list[0]], node1, self.exec_list)
                hotExchange.HotTrans(self.graphSet.GraphSet[graph].VerticesSet[dm_list[1]], node1, self.exec_list)
                hotExchange.HotTrans(self.graphSet.GraphSet[graph].VerticesSet[dm_list[2]], node1, self.exec_list)
                hotExchange.HotTrans(self.graphSet.GraphSet[graph].VerticesSet[dm_list[3]], node1, self.exec_list)
            elif dm in self.translated:
                self.translated.append(dm)

                hotExchange.HotTrans(self.graphSet.GraphSet[graph].VerticesSet[um_list[0]], node2, self.exec_list)
                hotExchange.HotTrans(self.graphSet.GraphSet[graph].VerticesSet[um_list[1]], node2, self.exec_list)
                hotExchange.HotTrans(self.graphSet.GraphSet[graph].VerticesSet[um_list[2]], node2, self.exec_list)
                hotExchange.HotTrans(self.graphSet.GraphSet[graph].VerticesSet[um_list[3]], node2, self.exec_list)
            
        for i in self.exec_list:
            i.start()
        for i in self.exec_list:
            i.join(600)
        return True