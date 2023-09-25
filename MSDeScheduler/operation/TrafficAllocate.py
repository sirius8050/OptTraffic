import os
import sys
import time
from textwrap import indent
import numpy as np
import copy
from typing import Dict, List, Tuple
from ..kube_tool.kubectl import get_PODList_namespace
from MSDeScheduler.metrics.TrafficGraph import Graph
from MSDeScheduler.kube_tool.kubectl import get_POD_Node_namespace


class TrafficAllocate:
    def __init__(self, graph: Graph):
        self.graph = graph
        # node: pod
        self.edge = {}
        # print("输出全部结点")
        # for i in self.graph.VerticesSet.keys():
        #     print(self.graph.VerticesSet[i].Name, ':', self.graph.VerticesSet[i].NodeName)

    # 此函数目的是为了将Pod Name翻译成iptables中对应的SEP Name
    def __PODtoSEP(self, pod: str, service: str):
        # print(self.graph.MSName, service)
        SVC = ''.join(os.popen("sudo iptables -t nat -nvL KUBE-SERVICES |"
                               " grep \"" + self.graph.MSName + "/" + service + " \" | awk '{print $3}' | sed -n '2p'"))[:-1]
        SEPs = ''.join(os.popen("sudo iptables -t nat -nvL " + SVC + " | awk '{print $3}' | sed  '1,2d'"))[:-1].split(
            '\n')

        IP = ''.join(
            os.popen("kubectl get pod -o wide -n " + self.graph.MSName + " | grep -E '"
                     + pod + " .*Running' | awk '{print $6}'"))[:-1]
        for sep in SEPs:
            ip = ''.join(os.popen("sudo iptables -t nat -nvL " + sep + " | awk '{print $8}' | sed -n '3p'"))[:-1]
            if IP == ip:
                return sep
        return None

    def __PODtoSVC(self, service: str):
        SVC = ''.join(os.popen("sudo iptables -t nat -nvL KUBE-SERVICES |"
                               " grep \"" + self.graph.MSName + "/" + service + " \" | awk '{print $3}' | sed -n '2p'"))[:-1]
        return SVC

    def __iptables(self, link: str):
        """
        :param link: str1~str2
        :return: None
        代表从str1到str2的所有链路需要进行流量分配
        """
        # 寻找需要TA的所有边，从service name到pod name
        um, dm = link[:link.find('~')], link[link.find('~') + 1:]
        print(um, dm)
        um_list, dm_list = [], []
        vertices_set = get_PODList_namespace(self.graph.MSName)

        if None in self.graph.VerticesSet.keys():
            del self.graph.VerticesSet[None]
        for i in vertices_set:
            if um == i[:len(um)] and i[len(um)] == '-':
                # print(i)
                um_list.append(i)
            if dm == i[:len(dm)] and i[len(dm)] == '-':
                # print(i)
                dm_list.append(i)

        # 找到所有Pod所在的Node。筛选所需的Pod
        pod_node = get_POD_Node_namespace(self.graph.MSName)

        keys = copy.copy(list(pod_node.keys()))
        for i in keys:
            if i not in um_list and i not in dm_list:
                del pod_node[i]

        # 匹配组生成
        # {node:[[UM PODs], [DM PODs]]}
        node_um_dm: Dict[str, List[List[str], List[str]]] = {}
        for i in pod_node.keys():
            if i not in node_um_dm.keys():
                node_um_dm[pod_node[i]] = [[], []]

        for i in um_list:
            node_um_dm[pod_node[i]][0].append(i)
        for i in dm_list:
            node_um_dm[pod_node[i]][1].append(i)

        # 流量比例初始化。设置edge字典记录所有边流量比例
        um, dm = np.ones(len(um_list)), np.zeros(len(dm_list))

        # 计算need值
        need = float(len(um_list)) / float(len(dm_list))

        for node in node_um_dm.keys():
            # 判断匹配组内是否上游下游容器都非空，即可以本机通信
            if len(node_um_dm[node][0]) != 0 and len(node_um_dm[node][1]) != 0:
                # 判断组内是否够流量需求， 若够
                if len(node_um_dm[node][0]) / len(node_um_dm[node][1]) >= need:
                    for j in node_um_dm[node][1]:
                        self.edge[node + '~' + j] = need / len(node_um_dm[node][0])
                    for i in node_um_dm[node][0]:
                        for j in node_um_dm[node][1]:
                            um[um_list.index(i)] = um[um_list.index(i)] - need / len(node_um_dm[node][0])
                            dm[dm_list.index(j)] = dm[dm_list.index(j)] + need / len(node_um_dm[node][0])
                # 若组内提供的流量不够需求
                else:
                    for j in node_um_dm[node][1]:
                        self.edge[node + '~' + j] = 1 / len(node_um_dm[node][1])
                    for i in node_um_dm[node][0]:
                        for j in node_um_dm[node][1]:
                            um[um_list.index(i)] = um[um_list.index(i)] - 1 / len(node_um_dm[node][1])
                            dm[dm_list.index(j)] = dm[dm_list.index(j)] + 1 / len(node_um_dm[node][1])

        # 此时所有匹配组内的流量已经分配完毕。现在分配匹配组之间的跨节点流量
        # 从所有dm pod出发，判断哪些dm pod还没有接收到目标流量。然后再判断所有结点内的um pod。若有剩余流量，则分配
        for dm_i in dm_list:
            if dm[dm_list.index(dm_i)] < need:
                # 每个机器的内的um pod有相同的分配比例。适应iptables特性
                for node_i in node_um_dm.keys():
                    # 寻找到一个没有分配完上游的机器
                    if len(node_um_dm[node_i][0]) > 0:
                        if um[um_list.index(node_um_dm[node_i][0][0])] > 0:
                            # 机器中上游容器流量不够。
                            if um[um_list.index(node_um_dm[node_i][0][0])] * len(node_um_dm[node_i][0]) \
                                    <= need - dm[dm_list.index(dm_i)]:
                                dm[dm_list.index(dm_i)] = dm[dm_list.index(dm_i)] \
                                                          + um[um_list.index(node_um_dm[node_i][0][0])] \
                                                          * len(node_um_dm[node_i][0])
                                if um[um_list.index(node_um_dm[node_i][0][0])] > 0:
                                    self.edge[node_i + '~' + dm_i] = um[um_list.index(node_um_dm[node_i][0][0])]
                                for i in node_um_dm[node_i][0]:
                                    um[um_list.index(i)] = 0
                            # 机器中上游容器流量不够
                            else:
                                for i in node_um_dm[node_i][0]:
                                    um[um_list.index(i)] = um[um_list.index(i)] \
                                                           - (need - dm[dm_list.index(dm_i)]) \
                                                           / len(node_um_dm[node_i][0])
                                if (need - dm[dm_list.index(dm_i)]) \
                                        / len(node_um_dm[node_i][0]) > 0:
                                    self.edge[node_i + '~' + dm_i] = (need - dm[dm_list.index(dm_i)]) \
                                                                     / len(node_um_dm[node_i][0])
                                dm[dm_list.index(dm_i)] = need

    def ExecuteNode(self, link: str):
        # {node:{sep:ratio}}
        self.__iptables(link)
        print(self.edge)
        sep_ratio = {}
        um, dm = link[:link.find('~')], link[link.find('~') + 1:]
        svc = self.__PODtoSVC(dm)
        for node_sep in self.edge.keys():
            node = node_sep[:node_sep.find('~')]
            pod = node_sep[node_sep.find('~') + 1:]
            while True:
                sep = self.__PODtoSEP(pod, dm)
                if sep is not None:
                    break
                time.sleep(1)
            ratio = self.edge[node_sep]
            if node not in sep_ratio.keys():
                sep_ratio[node] = {}
            if sep not in sep_ratio[node].keys():
                sep_ratio[node][sep] = ratio

        print(sep_ratio)
        for node in sep_ratio.keys():
            if not os.path.exists('/tmp/iptables'):
                os.system('mkdir /tmp/iptables')
            if os.path.exists('/tmp/iptables/' + node + '.sh'):
                os.system('rm /tmp/iptables/' + node + '.sh')
            f = open('/tmp/iptables/' + node + '.sh', 'w')
            all_ratio = 1
            for sep in sep_ratio[node].keys():
                if list(sep_ratio[node].keys()).index(sep) == 0:
                    # old = f.read()
                    # f.seek(0)
                    all_ratio = sep_ratio[node][sep]
                    f.write("sudo iptables -t nat -I " + svc + " 1 -s 0.0.0.0/0 -j " + sep + " \n")
                    # f.write(old)
                else:
                    # old = f.read()
                    # f.seek(0)
                    all_ratio += sep_ratio[node][sep]
                    f.write("sudo iptables -t nat -I " + svc + " 1 -s 0.0.0.0/0 -j " + sep +
                            " -m statistic --mode random  --probability " + str(
                        sep_ratio[node][sep] / all_ratio) + " \n")
                    # f.write(old)
                    # sudo iptables -t nat -I KUBE-SVC-KVWZRLJ3RRU55EYE 1 -s 0.0.0.0/0 -j KUBE-SEP-5EMJYGBVFF6DIW4U -m statistic --mode random  --probability 0.17
                # print(sep_ratio[node][sep], all_ratio)

            f.close()
            os.system('scp /tmp/iptables/{node1}.sh {node2}:/tmp/{node3}.sh'.format(node1=node, node2=node, node3=node))
            os.system("ssh {node} 'bash /tmp/{node1}.sh'".format(node=node, node1=node))
            # os.system("ssh {node} 'sh /tmp/{node1}.sh'".format(node=node, node1=node))
            # os.system("ssh {node} 'bash /tmp/{node1}.sh'".format(node=node, node1=node))

