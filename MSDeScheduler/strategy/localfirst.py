import os
import random
from time import time
import requests
import copy
from typing import Dict, List, Tuple
from MSDeScheduler.operation.HotExchange import operate
from MSDeScheduler.metrics.TrafficGraph import Vertices, Graph, GraphSet, Edge
from MSDeScheduler.metrics.ClusterStatus import NodeStatus, NodeStatusSet


def get_node_cpu_spend(node):
    result = []
    for node_i in node:
        data = ''.join(os.popen(f"kubectl describe node {node_i} | grep cpu | grep %"))
        per = data[data.index('(') + 1:data.index('%')]
        result.append(int(per))
    return result


class LocalizeHeavyTraffic:
    """
    SOTA 方法实现：寻找最大流量的跨节点链路，将其本地化。
    """

    def __init__(self, graphSet: GraphSet, nodeSet: NodeStatusSet):
        self.graphSet = graphSet
        self.nodeSet = nodeSet
        self.result: List[Edge] = []
        self.translated = []
        self.translatedMap = {}
        # 当跨节点流量小于Threshold时不进行流量本地化
        self.Threshold = 5000

    def choiceEdge(self):
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
                if i > self.Threshold:
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
                        hotExchange.HotTrans(link.DM, link.UM.NodeName)

                    # 如果DM已经出现or stateful
                    elif not (link.UM.MSName + '~' + link.UM.ServiceName in self.translated or link.UM.Stateful) \
                            and (link.DM.MSName + '~' + link.DM.ServiceName in self.translated or link.DM.Stateful):
                        self.translatedMap[link.UM.MSName + '~' + link.UM.ServiceName + '~' + link.DM.ServiceName] \
                            = link.DM.NodeName
                        self.translated.append(link.UM.MSName + '~' + link.UM.ServiceName)
                        hotExchange.HotTrans(link.UM, link.DM.NodeName)
                    # 如果都没有出现and not stateful
                    elif not (link.UM.MSName + '~' + link.UM.ServiceName in self.translated or link.UM.Stateful) \
                            and not (link.DM.MSName + '~' + link.DM.ServiceName in self.translated or link.DM.Stateful):
                        self.translatedMap[link.UM.MSName + '~' + link.UM.ServiceName + '~' + link.DM.ServiceName] \
                            = link.DM.NodeName
                        self.translated.append(link.UM.MSName + '~' + link.UM.ServiceName)
                        self.translated.append(link.UM.MSName + '~' + link.DM.ServiceName)
                        hotExchange.HotTrans(link.UM, link.DM.NodeName)

            # 若不是第一次出现这对service
            if link.UM.MSName + '~' + link.UM.ServiceName + '~' + link.DM.ServiceName in self.translatedMap.keys():
                print(link.UM.NodeName, self.translatedMap[
                    link.UM.MSName + '~' + link.UM.ServiceName + '~' + link.DM.ServiceName])
                # 如果UM
                if link.UM.NodeName == self.translatedMap[
                    link.UM.MSName + '~' + link.UM.ServiceName + '~' + link.DM.ServiceName] and \
                        link.DM.NodeName == self.translatedMap[
                    link.UM.MSName + '~' + link.UM.ServiceName + '~' + link.DM.ServiceName]:
                    pass
                    # return 0
                elif link.DM.NodeName == self.translatedMap[
                    link.UM.MSName + '~' + link.UM.ServiceName + '~' + link.DM.ServiceName] and not link.UM.Stateful:
                    hotExchange.HotTrans(link.UM, link.DM.NodeName)
                    # return 1
                elif link.UM.NodeName == self.translatedMap[
                    link.UM.MSName + '~' + link.UM.ServiceName + '~' + link.DM.ServiceName] and not link.DM.Stateful:
                    hotExchange.HotTrans(link.DM, link.UM.NodeName)
                elif not link.UM.Stateful and not link.DM.Stateful:
                    hotExchange.HotTrans(link.UM, link.DM.NodeName)
                    hotExchange.HotTrans(link.DM, link.UM.NodeName)

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
            percent = f.readline()
            pods = int(f.readline())
        percents = {}    
        for i in ['skv-node2', 'skv-node3', 'skv-node4', 'skv-node6', 'skv-node7']:
            percents[i] = int(percent.split(',')[['skv-node2', 'skv-node3', 'skv-node4', 'skv-node6', 'skv-node7'].index(i)])
        # percents = {'skv-node2': 2, 'skv-node3': 14, 'skv-node4': 0, 'skv-node6': 2, 'skv-node7': 2}
        for i in percents.keys():
            percents[i] = percents[i] + pods
        for i in self.result:
            hotExchange = operate(self.graphSet, self.graphSet.GraphSet[i.UM.MSName], self.nodeSet)
            # time.sleep(0.5)
            um_node, dm_node = get_node_cpu_spend([i.UM.NodeName, i.DM.NodeName])
            # print('信息：',um_node, dm_node)
            if um_node < percents[i.UM.NodeName] and dm_node < percents[i.DM.NodeName]:
                if i.DM.Stateful:
                    print(i.UM.Name, i.DM.NodeName)
                    if trans_able(i, 0):
                        hotExchange.HotTrans(i.UM, i.DM.NodeName)
                elif i.UM.Stateful:
                    print(i.DM.Name, i.UM.NodeName)
                    if trans_able(i, 1):
                        hotExchange.HotTrans(i.DM, i.UM.NodeName)
                else:
                    if trans_able(i, 0):
                        hotExchange.HotTrans(i.UM, i.DM.NodeName)
                    elif trans_able(i, 1):
                        hotExchange.HotTrans(i.DM, i.UM.NodeName)
            elif um_node < percent:
                if not i.DM.Stateful:
                    if trans_able(i, 1):
                        hotExchange.HotTrans(i.DM, i.UM.NodeName)
            elif dm_node < percent:
                if not i.UM.Stateful:
                    if trans_able(i, 0):
                        hotExchange.HotTrans(i.UM, i.DM.NodeName)
        # 流量本地化完成
        return True

    def index(self, score_node, nums, score) -> int:
        pos = score_node.index(score, 0)
        while nums[pos] == 0:
            pos = score_node.index(score, pos + 1)
        return pos

    def scheduler(self, result, podName, srcNode):
        for i in range(len(result)):
            if result[i][0] in podName and result[i][1] == srcNode and result[i][3] > 0:
                result[i][3] -= 1
                return result[i][2]
        return ""

    def Localize(self):
        with open('/home/k8s/exper/zxz/MSScheduler_python/MSDeScheduler/strategy/percent.txt', 'r') as f:
            percent = int(f.read())
        nodes = ['skv-node2', 'skv-node3', 'skv-node4', 'skv-node6', 'skv-node7']
        cpu_use = get_node_cpu_spend(nodes)
        cpu_use = [int(0.8 * (percent - i)) for i in cpu_use]
        um_num, dm_num, cm_num = [0, 0, 0, 0, 0], [0, 0, 0, 0, 0], [0, 0, 0, 0, 0]
        for i in self.graphSet.GraphSet['social-network'].VerticesSet.keys():
            if 'nginx-thrift' in self.graphSet.GraphSet['social-network'].VerticesSet[i].Name:
                um_num[nodes.index(self.graphSet.GraphSet['social-network'].VerticesSet[i].NodeName)] += 1
            if 'home-timeline-service' in self.graphSet.GraphSet['social-network'].VerticesSet[i].Name:
                dm_num[nodes.index(self.graphSet.GraphSet['social-network'].VerticesSet[i].NodeName)] += 1
            if 'post-storage-service' in self.graphSet.GraphSet['social-network'].VerticesSet[i].Name:
                cm_num[nodes.index(self.graphSet.GraphSet['social-network'].VerticesSet[i].NodeName)] += 1
        schedule_result = []  # service,src node, des node, number
        score_node = [0, 0, 0, 0, 0]
        for i in range(5):
            if cpu_use[i] > 0:
                score_node[i] = max(um_num[i], dm_num[i]) + int((cpu_use[i] - abs(um_num[i] - dm_num[i])) / 2)
            else:
                score_node[i] = min(um_num[i], dm_num[i])
        o_score_node = score_node.copy()
        score_node = [i + random.random() / 10 for i in o_score_node]
        # score_node = [max(um_num[i], dm_num[i]) + int((cpu_use[i] - abs(um_num[i] - dm_num[i])) / 2) for i in range(5)]
        max_score, min_score = score_node.copy(), score_node.copy()
        max_score.sort(reverse=True)
        min_score.sort()
        print(um_num, dm_num)
        print(cpu_use)
        print(score_node)
        first_score = max_score[0]
        second_index = score_node.index(max_score[1])
        # second_index = 3
        mig_out, mig_in = 0, 0
        j = 0
        while True:
            if int(first_score) == um_num[score_node.index(first_score)] or um_num[score_node.index(first_score)] == 8:
                break
            print(um_num, dm_num)
            remains = int(first_score) - um_num[score_node.index(first_score)]
            if remains >= um_num[score_node.index(min_score[j])]:
                um_num[score_node.index(first_score)] += um_num[score_node.index(min_score[j])]
                schedule_result.append(['nginx-thrift', nodes[score_node.index(min_score[j])],
                                        nodes[score_node.index(first_score)],
                                        um_num[score_node.index(min_score[j])]])
                if second_index == score_node.index(min_score[j]):
                    mig_out += um_num[score_node.index(min_score[j])]
                um_num[score_node.index(min_score[j])] = 0
                j += 1
            else:
                um_num[score_node.index(first_score)] += remains
                schedule_result.append(['nginx-thrift', nodes[score_node.index(min_score[j])],
                                        nodes[score_node.index(first_score)],
                                        remains])
                if second_index == score_node.index(min_score[j]):
                    mig_out += remains
                um_num[score_node.index(min_score[j])] -= remains
        print(schedule_result)  # A
        j = 0
        while True:
            if int(first_score) == dm_num[score_node.index(first_score)] or dm_num[score_node.index(first_score)] == 8:
                break
            print(um_num, dm_num)
            remains = int(first_score) - dm_num[score_node.index(first_score)]
            pos = score_node.index(min_score[j])
            if remains >= dm_num[pos]:
                dm_num[score_node.index(first_score)] += dm_num[pos]
                schedule_result.append(['home-timeline-service', nodes[pos],
                                        nodes[score_node.index(first_score)],
                                        dm_num[pos]])
                if second_index == pos:
                    mig_out += um_num[score_node.index(min_score[j])]
                dm_num[pos] = 0
                j += 1
            else:
                dm_num[score_node.index(first_score)] += remains
                schedule_result.append(['home-timeline-service', nodes[pos],
                                        nodes[score_node.index(first_score)],
                                        remains])
                if second_index == pos:
                    mig_out += remains
                dm_num[pos] -= remains
        print(um_num, dm_num)
        # second_score = max_score[1]

        j = 0  # second_index
        while j < 5:
            if j == second_index:
                j += 1
                continue
            if j == score_node.index(first_score):
                j += 1
                continue
            if um_num[j] > 0:
                schedule_result.append(['nginx-thrift', nodes[j],
                                        nodes[second_index],
                                        um_num[j]])
                um_num[second_index] += um_num[j]
                mig_in += um_num[j]
                um_num[j] = 0
            if dm_num[j] > 0:
                schedule_result.append(['home-timeline-service', nodes[j],
                                        nodes[second_index],
                                        dm_num[j]])
                dm_num[second_index] += dm_num[j]
                mig_in += dm_num[j]
                dm_num[j] = 0
            j += 1
        print(um_num, dm_num, cm_num)
        # 处理另一个service对
        remains = cpu_use[second_index] + mig_out - mig_in
        print(mig_out, mig_in, remains)
        i = 0
        while i < 5:
            if remains == 0:
                break
            if i == second_index or cm_num[i] == 0:
                i += 1
                continue
            if remains >= cm_num[i]:
                schedule_result.append(['post-storage-service', nodes[i],
                                        nodes[second_index],
                                        cm_num[i]])
                remains -= cm_num[i]
            else:
                schedule_result.append(['post-storage-service', nodes[i],
                                        nodes[second_index],
                                        remains])
                remains = 0
            i += 1
        print(schedule_result)

        # pod 移动。这几个参数直接填进去
        hotExchange = operate(self.graphSet, self.graphSet.GraphSet['social-network'], self.nodeSet)
        key = copy.deepcopy(list(self.graphSet.GraphSet['social-network'].VerticesSet.keys()))
        for i in key:
            # print(i)
            if 'nginx-thrift' in self.graphSet.GraphSet['social-network'].VerticesSet[i].Name:
                # print(self.graphSet.GraphSet['social-network'].VerticesSet[i].Name, self.graphSet.GraphSet['social-network'].VerticesSet[i].NodeName)
                desNode = self.scheduler(schedule_result, self.graphSet.GraphSet['social-network'].VerticesSet[i].Name,
                                         self.graphSet.GraphSet['social-network'].VerticesSet[i].NodeName)
                if desNode != "":
                    hotExchange.HotTrans(self.graphSet.GraphSet['social-network'].VerticesSet[i], desNode)
                continue
            if 'home-timeline-service' in self.graphSet.GraphSet['social-network'].VerticesSet[i].Name:
                # print(self.graphSet.GraphSet['social-network'].VerticesSet[i].Name, self.graphSet.GraphSet['social-network'].VerticesSet[i].NodeName)
                desNode = self.scheduler(schedule_result, self.graphSet.GraphSet['social-network'].VerticesSet[i].Name,
                                         self.graphSet.GraphSet['social-network'].VerticesSet[i].NodeName)
                if desNode != "":
                    hotExchange.HotTrans(self.graphSet.GraphSet['social-network'].VerticesSet[i], desNode)
                continue
            if 'post-storage-service' in self.graphSet.GraphSet['social-network'].VerticesSet[i].Name:
                # print(self.graphSet.GraphSet['social-network'].VerticesSet[i].Name, self.graphSet.GraphSet['social-network'].VerticesSet[i].NodeName)
                desNode = self.scheduler(schedule_result, self.graphSet.GraphSet['social-network'].VerticesSet[i].Name,
                                         self.graphSet.GraphSet['social-network'].VerticesSet[i].NodeName)
                if desNode != "":
                    hotExchange.HotTrans(self.graphSet.GraphSet['social-network'].VerticesSet[i], desNode)
