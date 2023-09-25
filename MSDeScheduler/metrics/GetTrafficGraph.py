# ！/usr/bin/python3
# -*- coding: utf-8 -*-

import sys
import os
import copy
import requests
import threading
import eventlet
from typing import Dict, List
from .TrafficGraph import Vertices, Edge, Graph, GraphSet
from .GetTopology import GetTopology

# sys.path.append("/home/k8s/exper/zxz/MSScheduler_python/")
from ..kube_tool.kubectl import get_PODList_namespace

path = './MSDeScheduler/tmp_DAG/'

def InitTrafficGraphSet():
    # 获得全部json文件路径，去除其中非json文件
    json_list = os.listdir(path=path)
    for i in json_list:
        if i[-5:] != '.json':
            json_list.remove(i)

    # 给图列表添加图
    ms_graph_set = GraphSet()
    for json_path in json_list:
        # print(json_path)
        service = GetTopology(json_path, path)
        ms_graph_set.addGraph(Graph(list(service.keys())[0]))
        ms_graph_set.GraphSet[list(service.keys())[0]].GraphTopology = service[list(service.keys())[0]]

    for key_graph in ms_graph_set.GraphSet.keys():
        DAG = ms_graph_set.GraphSet[key_graph]
        PODList = get_PODList_namespace(DAG.MSName)
        # print(PODList)
        # # 给每个图添加结点
        for um in DAG.GraphTopology.keys():
            um_list = []
            for i in PODList:
                if um == i[:len(um)] and i[len(um)] == '-':
                    um_list.append(i)
            if len(um_list) == 1:
                DAG.addVertices(Vertices(um_list[0], 0, 0, um))
            else:
                for i in range(len(um_list)):
                    DAG.addVertices(Vertices(um_list[i], 0, 0, um))
                ver = [DAG.VerticesSet[um_list[i]] for i in range(len(um_list))]
                for i in range(len(ver)):
                    ver_copy = copy.copy(ver)
                    ver_copy.remove(ver[i])
                    ver[i].setReplicas(ver_copy)

        # 给每个图添加边
        for um in DAG.GraphTopology.keys():
            dm = DAG.GraphTopology[um]
            if isinstance(dm, str) and dm != '':
                um_list, dm_list = [], []
                for i in PODList:
                    if um == i[:len(um)] and i[len(um)] == '-':
                        um_list.append(i)
                    if dm == i[:len(dm)] and i[len(dm)] == '-':
                        dm_list.append(i)
                if len(um_list) == 1 and len(dm_list) == 1:
                    DAG.addVertices(Vertices(um_list[0], 0, 0, um))
                    DAG.addEdge(Edge(DAG.VerticesSet[um_list[0]], DAG.VerticesSet[dm_list[0]], 1))
                for i in um_list:
                    for j in dm_list:
                        DAG.addEdge(Edge(DAG.VerticesSet[i], DAG.VerticesSet[j], 1 / len(dm_list)))
                    edge_list = [DAG.EdgeSet[i + '~' + j] for j in dm_list]
                    for j in range(len(edge_list)):
                        edge_list_copy = copy.copy(edge_list)
                        edge_list_copy.remove(edge_list[j])
                        edge_list[j].setReplicas(edge_list_copy)
            elif isinstance(dm, list):
                for dm_i in dm:
                    um_list, dm_list = [], []
                    for i in PODList:
                        if um == i[:len(um)] and i[len(um)] == '-':
                            um_list.append(i)
                        if dm_i == i[:len(dm_i)] and i[len(dm_i)] == '-':
                            dm_list.append(i)

                    if len(um_list) == 1 and len(dm_list) == 1:
                        DAG.addVertices(Vertices(um_list[0], 0, 0, um))
                        DAG.addEdge(Edge(DAG.VerticesSet[um_list[0]], DAG.VerticesSet[dm_list[0]], 1))
                    for i in um_list:
                        for j in dm_list:
                            DAG.addEdge(Edge(DAG.VerticesSet[i], DAG.VerticesSet[j], 1 / len(dm_list)))
                        edge_list = [DAG.EdgeSet[i + '~' + j] for j in dm_list]
                        for j in range(len(edge_list)):
                            edge_list_copy = copy.copy(edge_list)
                            edge_list_copy.remove(edge_list[j])
                            edge_list[j].setReplicas(edge_list_copy)
        key_words = ['mongodb', 'redis', 'memcached', 'sql', 'jaeger']
        for vertice in DAG.VerticesSet.keys():
            for i in key_words:
                if i in DAG.VerticesSet[vertice].ServiceName:
                    DAG.VerticesSet[vertice].Stateful = True
                    break


        # init ServiceSet of graph
        for i in DAG.VerticesSet.keys():
            if DAG.VerticesSet[i].ServiceName not in list(DAG.ServiceSet.keys()):
                DAG.ServiceSet[DAG.VerticesSet[i].ServiceName] = [DAG.VerticesSet[i]]
            else:
                DAG.ServiceSet[DAG.VerticesSet[i].ServiceName].append(DAG.VerticesSet[i])
        if None in DAG.VerticesSet.keys():
            del DAG.VerticesSet[None]
    return ms_graph_set


def graphFlash(DAG: Graph):
    # flash traffic information in graph
    urlIn = "http://127.0.0.1:31200/api/v1/query?query=sum(irate(container_network_receive_bytes_total{" \
            "namespace='" + DAG.MSName + "'}[1m])) by (pod) "
    urlOut = "http://127.0.0.1:31200/api/v1/query?query=sum(irate(container_network_transmit_bytes_total{" \
             "namespace='" + DAG.MSName + "'}[1m])) by (pod) "
    response = requests.request('GET', urlIn)
    result = response.json()
    receive_value = {result['data']['result'][i]['metric']['pod']: float(result['data']['result'][i]['value'][1])
                     for i in range(len(result['data']['result']))}
    response = requests.request('GET', urlOut)
    result = response.json()
    transmit_value = {result['data']['result'][i]['metric']['pod']: float(result['data']['result'][i]['value'][1])
                      for i in range(len(result['data']['result']))}
    for i in receive_value.keys():
        if i in DAG.VerticesSet.keys():
            DAG.VerticesSet[i].TotalTrafficIn = receive_value[i]
    for i in transmit_value.keys():
        if i in DAG.VerticesSet.keys():
            DAG.VerticesSet[i].TotalTrafficOut = transmit_value[i]
    


    # flash CPU information in graph.
    urlPodResource = "http://127.0.0.1:31200/api/v1/query?query=kube_pod_container_resource_requests{namespace='" \
                     + DAG.MSName + "'}"
    urlPodMemoryUsed = "http://127.0.0.1:31200/api/v1/query?query=sum(container_memory_working_set_bytes{namespace='" \
                       + DAG.MSName + "'}) by (pod)"
    urlPodCPUUsed = "http://127.0.0.1:31200/api/v1/query?query=sum(container_memory_working_set_bytes{namespace='" \
                    + DAG.MSName + "'}) by (pod)"
    response = requests.request('GET', urlPodResource)
    result = response.json()
    result = result['data']['result']

    for i in result:
        if i['metric']['resource'] == 'cpu':
            if i['metric']['pod'] in DAG.VerticesSet.keys():
                DAG.VerticesSet[i['metric']['pod']].CPU_request = float(i['value'][1])
        elif i['metric']['resource'] == 'memory':
            if i['metric']['pod'] in DAG.VerticesSet.keys():
                DAG.VerticesSet[i['metric']['pod']].RAM_request = float(i['value'][1])

    response = requests.request('GET', urlPodMemoryUsed)
    result = response.json()
    result = result['data']['result']
    for i in result:
        if i['metric']['pod'] in DAG.VerticesSet.keys():
            DAG.VerticesSet[i['metric']['pod']].RAM_used = float(i['value'][1])

    response = requests.request('GET', urlPodCPUUsed)
    result = response.json()
    result = result['data']['result']
    for i in result:
        if i['metric']['pod'] in DAG.VerticesSet.keys():
            DAG.VerticesSet[i['metric']['pod']].CPU_used = float(i['value'][1])

    # Flash IP information
    pod_ip = {}
    pod_name = {}
    svc_ip = {}
    pod_info = ''.join(os.popen("kubectl get pod -n " + DAG.MSName
                                + " -o wide | awk '{print $1,$6,$7}' | sed '1d'"))[:-1].split()
    svc_info = ''.join(os.popen("kubectl get svc -n " + DAG.MSName
                                + " -o wide | awk '{print $1,$3}' | sed '1d'"))[:-1].split()

    # 修改pod name的格式，去掉k8s生成的唯一性编码
    # for i in range(int(len(pod_info) / 3)):
    #     pod_info[i * 3] = pod_info[i * 3][:4] + pod_info[i * 3][4:][:pod_info[i * 3][4:].index('-') + 2]

    # print(pod_info)
    for i in range(int(len(pod_info) / 3)):
        pod_ip[pod_info[i * 3]] = pod_info[i * 3 + 1]
        pod_name[pod_info[i * 3]] = pod_info[i * 3 + 2]
    for i in range(int(len(svc_info) / 2)):
        svc_ip[svc_info[i * 2]] = svc_info[i * 2 + 1]
    for i in pod_ip.keys():
        if i in DAG.VerticesSet.keys():
            DAG.VerticesSet[i].PodIP = pod_ip[i]
            DAG.VerticesSet[i].NodeName = pod_name[i]
            DAG.VerticesSet[i].MSName = DAG.MSName
    for i in DAG.VerticesSet.keys():
        for j in svc_ip.keys():
            if j == i[:len(j)] and i[len(j)] == '-':
                DAG.VerticesSet[i].ServiceIP = svc_ip[j]
    # print(pod_name)


def __getSize(a):
    if a[-2] == 'b':
        return int(float(a[:-2]) / 8)
    if a[-2] == 'K':
        return int(float(a[:-2]) * 1000)
    if a[-2] == 'M':
        return int(float(a[:-2]) * 1000000)
    if a[-2] == 'M':
        return int(float(a[:-2]) * 1000000000)
    return int(float(a[:-1]))


def breakRing(DAG: Graph, line: List[str]):
    """
    在两条line组成的ring中插入iftop监控所有流量
    :param DAG:
    :param line:  line 内保存的是Service name。不是Pod name
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
    minTotalTraffic = DAG.ServiceSet[line1[vert]][0].TotalTrafficIn + DAG.ServiceSet[line1[vert]][0].TotalTrafficOut
    for i in range(vert + 1, len(line1)):
        now = (DAG.ServiceSet[line1[i]][0].TotalTrafficIn
               + DAG.ServiceSet[line1[i]][0].TotalTrafficOut) * len(DAG.ServiceSet[line1[i]])
        if now < minTotalTraffic:
            vertice = line1[i]
            minTotalTraffic = now
            result = line[0]
    for i in range(vert + 1, len(line2)):
        now = (DAG.ServiceSet[line2[i]][0].TotalTrafficIn
               + DAG.ServiceSet[line2[i]][0].TotalTrafficOut) * len(DAG.ServiceSet[line2[i]])
        if now < minTotalTraffic:
            vertice = line2[i]
            minTotalTraffic = now
            result = line[1]

    thread = []
    for i in DAG.ServiceSet[vertice]:
        start = threading.Thread(target=insert_plug, args=(DAG, i.Name))
        thread.append(start)
        start.start()
    for i in thread:
        i.join()
    return result


def insert_plug(DAG: Graph, vertice):
    # vertice = 'user-mention-service-3-5fb678dd9c-6rc5q'
    ifLink = ''.join(os.popen("kubectl exec -n {namespace} {pod} -- cat /sys/class/net/eth0/iflink"
                              .format(namespace=DAG.MSName, pod=vertice)))[:-1]
    ipLink = ''.join(
        os.popen("ssh " + DAG.VerticesSet[vertice].NodeName + " ip link | grep " + ifLink + " | awk '{print $2}'"))[:-1]
    ipLink = ipLink[:ipLink.find('@')]
    eventlet.monkey_patch()
    flag = False
    # TODO:修改短期运行时启动监控为长期运行,以获得更加准确的监控，并且可以优化代码执行延时
    with eventlet.Timeout(3, False):  # 设置超时时间为2秒
        edgeTraffic = ''.join(os.popen("ssh " + DAG.VerticesSet[vertice].NodeName + " sudo iftop -i " + ipLink
                                       + " -t  -N -n -s 2 -L 50 | grep -A 1 -E '^   [0-9]'")).split()
        flag = True
    if not flag:
        return
    # 得到所有收发IP的流量统计
    edgeTrafficMap = {}
    # 统计所有name 与 name 之间的流量
    nameTrafficMap = {}
    for i in range(len(edgeTraffic)):
        if edgeTraffic[i] == '=>':
            edgeTrafficMap[edgeTraffic[i - 1] + '~' + edgeTraffic[i + 5]] = [__getSize(edgeTraffic[i + 2]),
                                                                             __getSize(edgeTraffic[i + 8])]
    PodIPSet, ServiceIPSet = [], []
    for i in DAG.VerticesSet.keys():
        if DAG.VerticesSet[i].PodIP not in PodIPSet:
            PodIPSet.append(DAG.VerticesSet[i].PodIP)
        if DAG.VerticesSet[i].ServiceIP not in ServiceIPSet:
            ServiceIPSet.append(DAG.VerticesSet[i].ServiceIP)
    for i in edgeTrafficMap.keys():
        a, b = i[:i.index('~')], i[i.index('~') + 1:]
        if a in ServiceIPSet or b in ServiceIPSet:
            if b in ServiceIPSet:
                a, b = b, a
                edgeTrafficMap[i][0], edgeTrafficMap[i][1] = edgeTrafficMap[i][1], edgeTrafficMap[i][0]
            um = None
            for pod_i in DAG.VerticesSet.keys():
                if DAG.VerticesSet[pod_i].PodIP == b:
                    um = DAG.VerticesSet[pod_i].Name
            for pod_i in DAG.VerticesSet.keys():
                if DAG.VerticesSet[pod_i].ServiceIP == a:
                    if um + '~' + pod_i in DAG.EdgeSet.keys():
                        nameTrafficMap[um + '~' + pod_i] = [edgeTrafficMap[i][0] * DAG.EdgeSet[um + '~' + pod_i].Ratio,
                                                            edgeTrafficMap[i][1] * DAG.EdgeSet[um + '~' + pod_i].Ratio]
        else:
            um, dm = None, None
            for pod_i in DAG.VerticesSet.keys():
                if DAG.VerticesSet[pod_i].PodIP == a:
                    um = DAG.VerticesSet[pod_i].Name
            for pod_i in DAG.VerticesSet.keys():
                if DAG.VerticesSet[pod_i].PodIP == b:
                    dm = DAG.VerticesSet[pod_i].Name
            if um is not None and dm is not None:
                if um + '~' + dm in DAG.EdgeSet.keys():
                    nameTrafficMap[um + '~' + dm] = [edgeTrafficMap[i][0], edgeTrafficMap[i][1]]
                else:
                    nameTrafficMap[dm + '~' + um] = [edgeTrafficMap[i][1], edgeTrafficMap[i][0]]

    # break ring 值填充
    send, receive = 0, 0
    for i in nameTrafficMap.keys():
        if i[:i.index('~')] == vertice:
            send += nameTrafficMap[i][0]
            receive += nameTrafficMap[i][1]
        elif i[i.index('~') + 1:] == vertice:
            send += nameTrafficMap[i][1]
            receive += nameTrafficMap[i][0]
    for i in nameTrafficMap.keys():
        if send != 0:
            DAG.EdgeSet[i].Send = nameTrafficMap[i][0] / send * DAG.VerticesSet[vertice].TotalTrafficOut
        if receive != 0:
            DAG.EdgeSet[i].Receive = nameTrafficMap[i][1] / receive * DAG.VerticesSet[vertice].TotalTrafficIn
    DAG.VerticesSet[vertice].insert = True


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
            if i == j[:len(i)] and j[len(i)] == '-':
                if i in service.keys():
                    service[i].append(j)
                else:
                    service[i] = [j]
        # if topo[i] is not None:
        #     graph[i+'~'+topo[i]] = 0
    for i in service.keys():
        # 节点收、发总数
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
            if isinstance(j, List):
                if i in j:
                    time += 1
            if isinstance(j, str):
                if i == j:
                    time += 1
        if time == 1:
            OneDegree.append(i)
        else:
            MoreDegree[i] = time

    for i in topo.keys():
        for j in insertedPods:
            if i == j.ServiceName:
                SolvedSet.append(i)
                if i in OneDegree:
                    OneDegree.remove(i)
                    SolvedSet.append(i)
                if i in MoreDegree.keys():
                    del MoreDegree[i]
                    for k in list(MoreDegree.keys()).copy():
                        if k not in MoreDegree.keys():
                            continue
                        if k in topo[i] or i in topo[k]:
                            MoreDegree[k] = MoreDegree[k] - 1
                            if MoreDegree[k] == 1:
                                del MoreDegree[k]
                                OneDegree.append(k)

    # 给与SolvedSet中节点相连的节点减去一个度
    for i in SolvedSet.copy():
        MergedVertices[i] = [0, 0]
        if i in OneDegree:
            OneDegree.remove(i)
            SolvedSet.append(i)
        if i in MoreDegree.keys():
            MoreDegree[i] -= 1
            if MoreDegree[i] <= 1:
                OneDegree.append(i)
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
            um_list, dm_list = [], []
            for k in DAG.VerticesSet.keys():
                if topo[i] == j or j in topo[i]:
                    if i == k[:len(i)] and k[len(i)] == '-':
                        um_list.append(k)
                    if j == k[:len(j)] and k[len(j)] == '-':
                        dm_list.append(k)
                elif i in topo[j] or i == topo[j]:
                    if i == k[:len(i)] and k[len(i)] == '-':
                        dm_list.append(k)
                    if j == k[:len(j)] and k[len(j)] == '-':
                        um_list.append(k)
            MergeTraffic[i + '=>' + j] = 0
            MergeTraffic[j + '=>' + i] = 0
            for um in um_list:
                for dm in dm_list:
                    MergeTraffic[i + '=>' + j] += DAG.EdgeSet[um + '~' + dm].Send
                    MergeTraffic[j + '=>' + i] += DAG.EdgeSet[um + '~' + dm].Receive

    # 处理度为1的节点。找到度1相邻节点
    while len(OneDegree) != 0:
        i = OneDegree[0]
        OneDegree.remove(i)
        SolvedSet.append(i)
        conn_set = []
        for j in topo.keys():
            if isinstance(topo[i], List):
                if j in topo[i]:
                    conn_set.append(j)
            elif j == topo[i]:
                conn_set.append(j)
            if isinstance(topo[j], List):
                if i in topo[j]:
                    conn_set.append(j)
            elif i == topo[j]:
                conn_set.append(j)
        
        for j in conn_set:
            if j in OneDegree:
                MergeTraffic[i + '=>' + j] = MergedVertices[i][1]
                MergeTraffic[j + '=>' + i] = MergedVertices[i][0]
                MergedVertices[j] = [0, 0]
                OneDegree.remove(j)
                SolvedSet.append(j)
            if j in MoreDegree:
                # print(MergedVertices.keys())
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
        um_list, dm_list = [], []
        for j in DAG.VerticesSet.keys():
            if a == j[:len(a)] and j[len(a)] == '-':
                um_list.append(j)
            if b == j[:len(b)] and j[len(b)] == '-':
                dm_list.append(j)
        # print(um_list, dm_list)
        for a in um_list:
            for b in dm_list:
                service = DAG.VerticesSet[a].ServiceName + '=>' + DAG.VerticesSet[b].ServiceName
                # print(a, b, service)
                if a + '~' + b in DAG.EdgeSet.keys():
                    DAG.EdgeSet[a + '~' + b].Send = DAG.EdgeSet[a + '~' + b].Ratio / len(um_list)\
                                                    * MergeTraffic[service]
                elif b + '~' + a in DAG.EdgeSet.keys():
                    DAG.EdgeSet[b + '~' + a].Receive = DAG.EdgeSet[b + '~' + a].Ratio / len(um_list)\
                                                       * MergeTraffic[service]


