'''
    解析所有文件，分析出其中的调用图。形成调用图数据结构。
    求出每个pod收发的总流量。递推出真实值。
    求解偏差。
'''
import os
import json
import copy
import threading
from typing import Dict, List, NewType


def find_ip(name: str):
    pod_ip, svc_ip = '', ''
    f = open("/home/k8s/exper/zxz/old/zxz/MSScheduler_python/trafficmonitor/pod.log", "r")
    line = f.readline()
    while line:
        if name in line:
            line_list = list(line.split(' '))
            # print(line_list)
            for i in line_list:
                if i[:3] == '10.':
                    pod_ip = i
                    break
            break
        line = f.readline()
    f.close()

    f = open("/home/k8s/exper/zxz/old/zxz/MSScheduler_python/trafficmonitor/svc.log", "r")
    line = f.readline()
    while line:
        line_list = list(line.split(' '))
        if line_list[0] in name:
            for i in line_list:
                if i[:3] == '10.':
                    svc_ip = i
                    break
            break
        line = f.readline()
    f.close()

    return pod_ip, svc_ip


# 数据结构
class Vertices:
    def __init__(self, Name: str, veth:str, pod_ip, svc_ip):
        self.Name = Name
        self.ServiceName = Name
        self.Veth = veth
        self.IP = pod_ip
        self.SVCIP = svc_ip
        self.TotalTrafficIn = 0
        self.TotalTrafficOut = 0
        self.insert = False


class Edge:
    def __init__(self, UM: Vertices, DM: Vertices):
        self.UM = UM
        self.DM = DM
        self.Name = UM.Name + '~' + DM.Name
        self.Send1 = 0
        self.Send2 = 0
        self.Receive1 = 0
        self.Receive2 = 0
        self.PSend = 0
        self.PReceive = 0
        self.Ratio = 1


class Graph:
    def __init__(self, Name: str):
        self.MSName = Name
        # Name:Object
        self.VerticesSet: Dict[str, Vertices] = {}
        # Name:[Object]
        self.ServiceSet: Dict[str, List[Vertices]] = {}
        # Name:Object
        self.EdgeSet: Dict[str, Edge] = {}
        # Name:Name
        self.GraphTopology = {}

    def addVertices(self, vert: Vertices):
        if vert.Name is not None:
            self.VerticesSet[vert.Name] = vert

    def addEdge(self, edge: Edge):
        self.EdgeSet[edge.Name] = edge

    def findHead(self):
        head = []
        value = []
        for i in self.GraphTopology.values():
            if isinstance(i, List):
                for j in i:
                    if j not in value:
                        value.append(j)
            if isinstance(i, str):
                if i not in value:
                    value.append(i)
        for i in self.GraphTopology.keys():
            if i not in value:
                head.append(i)
        return head


# 读取文件名
path = '/home/k8s/exper/zxz/old/zxz/MSScheduler_python/trafficmonitor/iftop/'
files = os.listdir(path=path)

pods, veths = [], []

for i in files:
    pods.append(i[:i.find('-veth')])
    veths.append(i[i.find('veth'):i.find('.log')])

# 数据结构创建
graph = Graph('social-network')
for j in range(len(pods)):
    pod = pods[j]
    pod_svc_ip = find_ip(pod)
    # 修改pod name为svc name
    k = 0
    for i in range(len(pod)):
        if pod[-i] == '-':
            k += 1
            if k == 2:
                pod = pod[:-i]
                break
    graph.addVertices(Vertices(pod, veths[k], pod_svc_ip[0], pod_svc_ip[1]))
print('Create Graph Done!')


# 获得拓扑
def GetTopology(path):
    TopologyPath = path
    Topology = open(TopologyPath, 'r')
    topo = json.load(Topology)
    Topology.close()

    data = topo
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

topo = GetTopology('/home/k8s/exper/zxz/old/zxz/MSScheduler_python/trafficmonitor/DAG.json')
graph.GraphTopology = topo
print("Topology Got!")


# 解析文件，边填充

def get_value(bandwidth):
    # bandwidth = bandwidth[:-1]
    # print(bandwidth)
    if bandwidth[-2] == 'G':
        return float(bandwidth[:-2]) * 10**9
    if bandwidth[-2] == 'M':
        return float(bandwidth[:-2]) * 10**6
    if bandwidth[-2] == 'K':
        return float(bandwidth[:-2]) * 10**3
    return float(bandwidth[:-1])

def find_pod(graph: Graph, IP: str):
    for ver in graph.VerticesSet.keys():
        if IP == graph.VerticesSet[ver].IP or IP == graph.VerticesSet[ver].SVCIP:
            return ver


def pod_to_svc(pod):
    k = 0
    for i in range(len(pod)):
        if pod[-i] == '-':
            k += 1
            if k == 2:
                pod = pod[:-i]
                break
    return pod

for j in range(len(pods)):
    pod_copy = pods[j]
    f = open(path + pod_copy + '-' + veths[j] + '.log', 'r')
    pod_copy = pod_to_svc(pod_copy)

    line1, line2 = '', ''
    while True:
        pod = pod_copy
        line1 = f.readline()
        if not line1 or line1[0] == '-':
            break
        line2 = f.readline()
        line1, line2 = list(line1.split()), list(line2.split())
        line1 = line1[1:]
        if graph.VerticesSet[pod].IP == line1[0] or graph.VerticesSet[pod].SVCIP == line1[0]:
            ano_pod = find_pod(graph=graph, IP=line2[0])
            if ano_pod is not None and pod in graph.GraphTopology.keys():
                graph.VerticesSet[pod].TotalTrafficOut += get_value(line1[-1])
                graph.VerticesSet[pod].TotalTrafficIn += get_value(line2[-1])
                if isinstance(graph.GraphTopology[pod], str):
                    if graph.GraphTopology[pod] != ano_pod:
                        pod, ano_pod = ano_pod, pod
                        line1, line2 = line2, line1
                else:
                    if ano_pod not in graph.GraphTopology[pod]:
                        pod, ano_pod = ano_pod, pod
                        line1, line2 = line2, line1
                if pod + '~' + ano_pod not in graph.EdgeSet.keys():
                    graph.addEdge(Edge(graph.VerticesSet[pod], graph.VerticesSet[ano_pod]))

                if pod + '~' + ano_pod not in graph.EdgeSet.keys():
                    pod, ano_pod = ano_pod, pod
                    line1, line2 = line2, line1
                if graph.EdgeSet[pod + '~' + ano_pod].Send1 == 0 and graph.EdgeSet[pod + '~' + ano_pod].Receive1 == 0:
                    graph.EdgeSet[pod + '~' + ano_pod].Send1 += get_value(line1[-1])
                    graph.EdgeSet[pod + '~' + ano_pod].Receive1 += get_value(line2[-1])
                else:
                    graph.EdgeSet[pod + '~' + ano_pod].Send2 += get_value(line1[-1])
                    graph.EdgeSet[pod + '~' + ano_pod].Receive2 += get_value(line2[-1])
        else:
            ano_pod = find_pod(graph=graph, IP=line1[0])
            if ano_pod is not None and pod in graph.GraphTopology.keys():
                graph.VerticesSet[pod].TotalTrafficOut += get_value(line2[-1])
                graph.VerticesSet[pod].TotalTrafficIn += get_value(line1[-1])
                if isinstance(graph.GraphTopology[pod], str):
                    if graph.GraphTopology[pod] != ano_pod:
                        pod, ano_pod = ano_pod, pod
                        line1, line2 = line2, line1
                else:
                    if ano_pod not in graph.GraphTopology[pod]:
                        pod, ano_pod = ano_pod, pod
                        line1, line2 = line2, line1
                if pod + '~' + ano_pod not in graph.EdgeSet.keys():
                    graph.addEdge(Edge(graph.VerticesSet[pod], graph.VerticesSet[ano_pod]))

                if pod + '~' + ano_pod not in graph.EdgeSet.keys():
                    pod, ano_pod = ano_pod, pod
                    line1, line2 = line2, line1
                if graph.EdgeSet[pod + '~' + ano_pod].Send1 == 0 and  graph.EdgeSet[pod + '~' + ano_pod].Receive1 == 0:
                    graph.EdgeSet[pod + '~' + ano_pod].Send1 += get_value(line2[-1])
                    graph.EdgeSet[pod + '~' + ano_pod].Receive1 += get_value(line1[-1])
                else:
                    graph.EdgeSet[pod + '~' + ano_pod].Send2 += get_value(line2[-1])
                    graph.EdgeSet[pod + '~' + ano_pod].Receive2 += get_value(line1[-1])
    f.close()
print("Data Cleaning Done!")



# 解方程

def breakRing(DAG: Graph, line: List[str]):
    """
    在两条line组成的ring中插入iftop监控所有流量
    :param DAG:
    :param line:  line 内保存的是Pod name
    :return:
    """
    line1, line2 = line[0].split('~')[1:], line[1].split('~')[1:]
    result = line[0]
    # vertice 是上面的交汇点。line1[-1]是下面的交汇点。需要在环上选择一个vertice进行流量监控
    vert = 0
    vertice = None
    if line1[-1] == line2[-1]:
        for i in range(min(len(line1), len(line2))):
            if line1[i] != line2[i]:
                vert = i - 1
                vertice = line1[vert]
                break

    # 找到ring中具有最小流量的service中任意一个vertice，在这个vertice中插入iftop
    minTotalTraffic = DAG.VerticesSet[line1[vert]].TotalTrafficIn + DAG.VerticesSet[line1[vert]].TotalTrafficOut
    for i in range(vert + 1, len(line1)):
        now = DAG.VerticesSet[line1[i]].TotalTrafficIn + DAG.VerticesSet[line1[i]].TotalTrafficOut
        if now < minTotalTraffic:
            vertice = line1[i]
            minTotalTraffic = now
            result = line[0]

    for i in range(vert + 1, len(line2)):
        now = DAG.VerticesSet[line2[i]].TotalTrafficIn + DAG.VerticesSet[line2[i]].TotalTrafficOut
        if now < minTotalTraffic:
            vertice = line2[i]
            minTotalTraffic = now
            result = line[1]

    insert_plug(DAG=DAG, vertice=vertice)
    DAG.VerticesSet[vertice].insert=True
    return result


def insert_plug(DAG: Graph, vertice):
    for edge in DAG.EdgeSet.keys():
        if vertice in edge:
            DAG.EdgeSet[edge].PSend = DAG.EdgeSet[edge].Send1
            DAG.EdgeSet[edge].PReceive = DAG.EdgeSet[edge].Receive1


def route(DAG: Graph, topo, now, line, status: Dict[str, List[str]]):
    """
    递归的来监测自己.
    :param DAG:
    :param topo:
    :param now:
    :param line:
    :param status:
    :return:
    """
    line = line + '~' + now
    # status记录每个节点内部的路径
    status[now].append(line)
    if len(status[now]) > 1:
        # 直接在此处进行break ring操作
        line1, line2 = status[now][0].split('~')[1:], status[now][1].split('~')[1:]
        for i in range(min(len(line1), len(line2))):
            # 找到第一个不一样的节点，但是后面一个节点一样也不行。则前面有环没处理
            if line1[i] != line2[i]:
                if i != min(len(line1), len(line2)) - 1:
                    if line1[i + 1] == line2[i + 1]:
                        status[now].remove(status[now][0])
                        return
                else:
                    break
        # 如果头不相同不行
        if line1[0] != line2[0]:
            status[now].remove(status[now][0])
            return
        # 倒数第一个必然不相同，但是倒数第二个相同也不行？
        if line1[-2] == line2[-2]:
            status[now].remove(status[now][0])
            return
        lin = breakRing(DAG, status[now])
        status[now].remove(lin)
    Next = topo[now]
    if Next == '':
        return
    # 广度优先遍历
    if isinstance(Next, List):
        for i in Next:
            route(DAG, topo, i, line, status)
    else:
        route(DAG, topo, Next, line, status)


def CheckRing(DAG: Graph):
    """
    检查图中是否有环，一个图可能有几个head，从每一个head出发都检查一便。
    :param DAG: 待检查的图
    :return:
    """
    head = DAG.findHead()
    topo = DAG.GraphTopology
    status = {}
    for i in topo.keys():
        status[i]: Dict[str, List[str]] = []
    for i in head:
        route(DAG, topo, i, '', status)


def GraphMerge(DAG: Graph):
    """
    将以Pod为单位的图合并成以以Service的图
    :param DAG:
    :return:
    """
    graph = {}
    service = {}
    topo = DAG.GraphTopology
    for i in topo.keys():
        for j in DAG.VerticesSet.keys():
            if i in j:
                if i in service.keys():
                    service[i].append(j)
                else:
                    service[i] = [j]
        # if topo[i] is not None:
        #     graph[i+'~'+topo[i]] = 0
    for i in service.keys():
        # 节点发、收总数
        graph[i] = [0, 0]
        for j in service[i]:
            graph[i][0] += DAG.VerticesSet[j].TotalTrafficIn
            graph[i][1] += DAG.VerticesSet[j].TotalTrafficOut
            
    # for i in DAG.VerticesSet.keys():
    #     print('name:', i, " traffic",  str((DAG.VerticesSet[i].TotalTrafficOut + DAG.VerticesSet[i].TotalTrafficIn) / 1000))   
    # for i in graph.keys():
    #     print('name:', i, " traffic",  str((graph[i][0] + graph[i][1]) / 1000)) 
    # print(graph)
    return graph


def LineEquationSolution(DAG: Graph):
    """
    解线性方程组，将值传入图中
    应该先进行CheckRing操作，再解方程组
    :param DAG:
    :return:
    """
    global um_list
    topo = DAG.GraphTopology
    MergedVertices = GraphMerge(DAG)
    # MergeTraffic用于存整个service的流量，即所有Pod流量之和
    MergeTraffic: Dict[str, int] = {}
    insertedPods: List[Vertices] = []
    for i in DAG.VerticesSet.keys():
        if DAG.VerticesSet[i].insert:
            insertedPods.append(DAG.VerticesSet[i])
    # 下面三个数组对应解方程中三种状态。分别是度为1的节点，多度节点，已经获悉流量的节点
    ZeroDegree: List[str] = []
    OneDegree: List[str] = []
    MoreDegree: Dict[str, int] = {}
    SolvedSet: List[str] = []
    # 生成度为1的list和多度list
    for i in topo.keys():
        if isinstance(topo[i], List):
            time = len(topo[i])
        elif topo[i] != '':
            time = 1
        else:
            time = 0
        for j in topo.values():
            if i in j:
                time += 1
        if time == 1:
            OneDegree.append(i)
        else:
            MoreDegree[i] = time

    for i in topo.keys():
        for j in insertedPods:
            if i == j.ServiceName:
                SolvedSet.append(i)
                # 这句不可能成功
                # if i in OneDegree:
                #     OneDegree.remove(i)
                #     SolvedSet.append(i)
                
                # if i in MoreDegree.keys():
                #     del MoreDegree[i]
                #     for k in list(MoreDegree.keys()).copy():
                #         if k not in MoreDegree.keys():
                #             continue
                #         if k in topo[i] or i in topo[k]:
                #             MoreDegree[k] = MoreDegree[k] - 1
                #             if MoreDegree[k] == 1:
                #                 del MoreDegree[k]
                #                 OneDegree.append(k)

    # 给与SolvedSet中节点相连的节点减去一个度
    for i in SolvedSet.copy():
        # MergedVertices[i] = [0, 0]
        if i in OneDegree:
            OneDegree.remove(i)
            # SolvedSet.append(i)
        if i in MoreDegree.keys():
            MoreDegree[i] = 0
            del MoreDegree[i]
        # 与之相连节点
        conn_set = []
        # print(topo)
        for j in topo.keys():
            if j == i and topo[j] != '':
                if isinstance(topo[j], List):
                    conn_set.extend(topo[j])
                else:
                    conn_set.append(topo[j])
            if topo[j] == i or i in topo[j]:
                conn_set.append(j)

        for j in conn_set:
            if i + '~' + j in DAG.EdgeSet.keys():
                graph.VerticesSet[j].TotalTrafficOut -= DAG.EdgeSet[i + '~' + j].PSend
                graph.VerticesSet[j].TotalTrafficIn -= DAG.EdgeSet[i + '~' + j].PReceive
                MergedVertices[i][0] -= MergedVertices[j][1]
                MergedVertices[i][1] -= MergedVertices[j][0]
            else:
                graph.VerticesSet[j].TotalTrafficOut -= DAG.EdgeSet[j + '~' + i].PReceive
                graph.VerticesSet[j].TotalTrafficIn -= DAG.EdgeSet[j + '~' + i].PSend
                MergedVertices[j][0] -= MergedVertices[i][1]
                MergedVertices[j][1] -= MergedVertices[i][0]
            if j in MoreDegree:
                MoreDegree[j] -= 1
                if MoreDegree[j] == 1:
                    del MoreDegree[j]
                    OneDegree.append(j)
            um_list, dm_list = [], []
            for k in DAG.VerticesSet.keys():
                if topo[i] == j or j in topo[i]:
                    if i in k:
                        um_list.append(k)
                    if j in k:
                        dm_list.append(k)
                elif i in topo[j] or i == topo[j]:
                    if i in k:
                        dm_list.append(k)
                    if j in k:
                        um_list.append(k)
            MergeTraffic[i + '=>' + j] = 0
            MergeTraffic[j + '=>' + i] = 0
            for um in um_list:
                for dm in dm_list:
                    # MergedVertices[um][0] -= MergedVertices[dm][1]
                    # MergedVertices[um][1] -= MergedVertices[dm][0]
                    MergeTraffic[um + '=>' + dm] += DAG.EdgeSet[um + '~' + dm].Send1
                    MergeTraffic[dm + '=>' + um] += DAG.EdgeSet[um + '~' + dm].Receive1

     
    while len(OneDegree) != 0:
        ZeroDegree, OneDegree = OneDegree, ZeroDegree
        # 处理度为的节点。找到度1相邻节点
        while len(ZeroDegree) != 0:
            i = ZeroDegree[0]
            if i == "user-memcached":
                if i == "user-mention-service":
                    pass
            ZeroDegree.remove(i)
            SolvedSet.append(i)
            conn_set = []
            for j in topo.keys():
                if j in topo[i] and j not in SolvedSet:
                    conn_set.append(j)
                if i in topo[j] and j not in SolvedSet:
                    conn_set.append(j)

            for j in conn_set:
                if j in OneDegree:
                    MergeTraffic[i + '=>' + j] = MergedVertices[i][1]
                    MergeTraffic[j + '=>' + i] = MergedVertices[i][0]
                    MergedVertices[j] = [0, 0]
                    OneDegree.remove(j)
                    ZeroDegree.append(j)
                if j in MoreDegree:
                    MergeTraffic[i + '=>' + j] = MergedVertices[i][1]
                    MergeTraffic[j + '=>' + i] = MergedVertices[i][0]
                    MergedVertices[j][0] = max(0, MergedVertices[j][0] - MergedVertices[i][1])
                    MergedVertices[j][1] = max(0, MergedVertices[j][1] - MergedVertices[i][0])
                    MoreDegree[j] -= 1
                    if MoreDegree[j] <= 1:
                        OneDegree.append(j)
                        del MoreDegree[j]
        
    # 将MergedVertices中数据传入
    for i in MergeTraffic:
        # a => b: num
        # print(i)
        a, b = i[:i.index('=>')], i[i.index('=>') + 2:]

        # service = DAG.VerticesSet[a].ServiceName + '=>' + DAG.VerticesSet[b].ServiceName
        if a + '~' + b in DAG.EdgeSet.keys():
            DAG.EdgeSet[a + '~' + b].PSend = MergeTraffic[a + '=>' + b]
            DAG.EdgeSet[a + '~' + b].PReceive = MergeTraffic[b + '=>' + a]
        elif b + '~' + a in DAG.EdgeSet.keys():
            # print(666666)
            DAG.EdgeSet[b + '~' + a].PSend = MergeTraffic[b + '=>' + a]
            DAG.EdgeSet[b + '~' + a].PReceive = MergeTraffic[a + '=>' + b]

# for i in graph.VerticesSet.keys():
#     print(graph.VerticesSet[i].Name, graph.VerticesSet[i].IP, graph.VerticesSet[i].SVCIP)
for pod in graph.VerticesSet.keys():
    print(pod, '\t', graph.VerticesSet[pod].TotalTrafficIn, '\t',graph.VerticesSet[pod].TotalTrafficOut)
CheckRing(graph)
LineEquationSolution(graph)

result, pre = [], []
name = []
for edge in graph.EdgeSet.keys():
    print(f'{edge}\t{graph.EdgeSet[edge].Send1}\t{graph.EdgeSet[edge].Send2}\t{graph.EdgeSet[edge].PSend}')
    print(f'{edge}\t{graph.EdgeSet[edge].Receive1}\t{graph.EdgeSet[edge].Receive2}\t{graph.EdgeSet[edge].PReceive}')
    print('')
    name.append(edge)
    result.append(graph.EdgeSet[edge].Send1 + graph.EdgeSet[edge].Receive1)
    pre.append(graph.EdgeSet[edge].PSend + graph.EdgeSet[edge].PReceive)


for pod in graph.VerticesSet.keys():
    print(pod, '\t', graph.VerticesSet[pod].TotalTrafficIn, '\t',graph.VerticesSet[pod].TotalTrafficOut)

while len(result) > 0:
    if max(result) == 0:
        break
    print(name[result.index(max(result))], '\t',result[result.index(max(result))], '\t', 1-(pre[result.index(max(result))]/result[result.index(max(result))]))
    pre.remove(pre[result.index(max(result))])
    result.remove(max(result))
    