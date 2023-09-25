# ！/usr/bin/python3
# -*- coding: utf-8 -*-
import copy
import os


def get_PODList_namespace(namespace):
    PODInfo = ''.join(os.popen('kubectl get pod -n ' + namespace + ' -o wide | grep Running | grep -v add'))
    PODInfo = list(filter(None, PODInfo.split(' ')))
    # print(PODInfo)
    pod_list = [copy.copy(PODInfo[0])]
    for i in PODInfo:
        if i[:7] == '<none>\n' and len(i) > 7:
            pod = i[7:]
            pod_list.append(pod)
        if i[:6] == 'GATES\n' and len(i) > 6:
            pod = i[6:]
            pod_list.append(pod)
    return pod_list


def get_POD_Node_namespace(namespace):
    PODInfo = ''.join(os.popen('kubectl get pod -n ' + namespace + ' -o wide | grep Running | grep -v add '))
    PODInfo = list(filter(None, PODInfo.split(' ')))
    pod_node = {copy.copy(PODInfo[0]): copy.copy(PODInfo[6])}
    for i in range(len(PODInfo)):
        if PODInfo[i][:7] == '<none>\n' and i < len(PODInfo) - 7:
            pod = PODInfo[i][7:]
            pod_node[pod] = PODInfo[i+6]
        if PODInfo[i][:6] == 'GATES\n' and i < len(PODInfo) - 6:
            pod = PODInfo[i][6:]
            pod_node[pod] = PODInfo[i+6]
    return pod_node


