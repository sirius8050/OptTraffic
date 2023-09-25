# ！/usr/bin/python3
# -*- coding: utf-8 -*-
import os

import requests
from kubernetes import client, config
from kubernetes.client import api_client
from kubernetes.client.api import core_v1_api


# 返回所需要的信息，用于算法中


class KubernetesTools(object):
    def __init__(self):
        self.k8s_url = 'https://127.0.0.1:6443'

    # 获取token
    def get_token(self):
        with open('/token.txt', 'r') as file:
            Token = file.read().strip('\n')
            return Token

    # 获取API的CoreV1Api版本对象

    def get_api(self):
        configuration = client.Configuration()
        configuration.host = self.k8s_url
        configuration.verify_ssl = False
        configuration.api_key = {"authorization": "Bearer " + self.get_token()}
        client1 = api_client.ApiClient(configuration=configuration)
        api = core_v1_api.CoreV1Api(client1)
        return api

    # 获取命名空间
    def get_namespace_list(self):
        api = self.get_api()
        namespace_list = []
        for ns in api.list_namespace().items:
            namespace_list.append(ns.metadata.name)
        return namespace_list

    def get_pod_list_namespace(self, namespace: str) -> list:
        api = self.get_api()
        pod_list = []
        for pod in api.list_namespaced_pod(namespace=namespace).items:
            pod_list.append(pod)
        return pod_list

    def get_node_list(self):
        api = self.get_api()
        node_list = []
        for ns in api.list_node().items:
            node_list.append(ns.metadata.name)
        return node_list

    # 获得每个具有MSname标签的pod，获得指定MSname的所有Pod所在的node name。
    # 输出为pod_node，这个为一个map。key为pod name，value为node name。
    def get_pod_node(self, MSname):
        api = self.get_api()
        pod_node = {}
        for pod in api.list_pod_for_all_namespaces().items:
            if 'MSname' in pod.metadata.labels.keys():
                if MSname == pod.metadata.labels['MSname']:
                    # 判断pod_name是否有生成的保证唯一性的id在里面
                    if pod.metadata.generate_name == None:
                        pod_name = pod.metadata.name
                    else:
                        pod_name = pod.metadata.name
                        for i in range(len(pod_name)):
                            num = 0
                            if pod_name[-i] == '-':
                                num += 1
                                if num == 2:
                                    pod_name = pod_name[:-i]
                                    break
                    pod_node[pod_name] = pod.spec.node_name
        return pod_node

    def get_CPUinfo_pod(self, pod: str):
        api = self.get_api()
        api.list_node()

if __name__ == '__main__':
    namespace_list = KubernetesTools()
    print(namespace_list)

