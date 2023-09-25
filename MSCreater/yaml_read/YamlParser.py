
import copy
import time
import os
import random
from json import load

import yaml


def generate(inPath, outPath, MSname, machine=0):
    # 构建三个空列表
    YamlDeploymentStateless, YamlDeploymentStateful, YamlService, YamlOthers = [], [], [], []

    # 将三种类型的yaml文件转换的map结构放入三个列表中
    with open(inPath, encoding='utf-8') as f:
        docs = yaml.load_all(f.read(), Loader=yaml.FullLoader)
        for doc in docs:
            if doc['kind'] == 'Service':
                YamlService.append(doc)
                continue
            if doc['kind'] == 'Deployment' or doc['kind'] == 'Pod':
                YamlDeploymentStateless.append(doc)
                YamlDeploymentStateful.append(doc)
                continue
            YamlOthers.append(doc)
        
    # 接下来对三种不同的yaml文件需要做不同的处理。
    # 首先对Others直接保存为yaml文件，这一般是处理Pod相关和Service相关的yaml配置。
    # 根据Deployment判断副本个数，若副本个数为1，或者kind为Pod也可以不需要多余处理。若副本数量大于1，
    # 则需要将多实例转换为多个独立的配置。并且Service也需要进行相应的处理。

    for deployment in YamlDeploymentStateless.copy():
        YamlDeploymentStateless.remove(deployment.copy())
        YamlDeploymentStateful.remove(deployment.copy())
        deployment['metadata']['labels']['MSname'] = MSname
        deployment['spec']['selector']['matchLabels']['MSname'] = MSname
        deployment['spec']['template']['metadata']['labels']['MSname'] = MSname
        YamlDeploymentStateless.append(deployment.copy())
        YamlDeploymentStateful.append(deployment.copy())
        # 若为Pod类型或者副本数为1则不进行处理
        if deployment['kind'] == 'Pod':
            continue
        if deployment['kind'] == 'Deployment':
            if deployment['spec']['replicas'] > 1:
                # 获得标签值
                labels = deployment['metadata']['labels'].copy()
                YamlDeploymentStateless.remove(deployment)
                YamlDeploymentStateful.remove(deployment)
                # 若为多副本，将副本的序号加到标签的最后面。只需要修改Name就好了，不需要修改标签值。
                replica_number = int(deployment['spec']['replicas'])
                deployment['spec']['replicas'] = 1

                for replica_th in range(replica_number):
                    node_set = ['skv-node2', 'skv-node3', 'skv-node4', 'skv-node6', 'skv-node7']
                    # node_set = ['skv-node2']

                    deployment_copy = copy.deepcopy(deployment)
                    labels_copy = labels.copy()
                    labels_copy['more-replicas'] = 'v' + str(replica_th)
                    labels_copy['MSname'] = MSname
                    deployment_copy['metadata']['labels'] = labels_copy.copy()
                    deployment_copy['metadata']['name'] += '-' + str(replica_th)

                    if machine:
                        deployment_copy['spec']['template']['spec']['nodeName'] = node_set[random.randint(0, machine-1)]

                    deployment_copy['spec']['selector']['matchLabels'] = labels_copy.copy()
                    deployment_copy['spec']['template']['metadata']['labels'] = labels_copy.copy()
                    deployment_copy['spec']['template']['spec']['containers'][0]['resources'] = {'limits': {'cpu': '500m', 'memory': '500Mi'},
                     'requests': {'cpu': '500m', 'memory': '500Mi'}}
                    # del deployment_copy['spec']['template']['spec']['containers'][0]['resources']
                    YamlDeploymentStateless.append(deployment_copy.copy())
            else:
                stateful = ['mongodb', 'redis', 'memcached', 'jaeger']
                for state in stateful:
                    deployment_copy = copy.deepcopy(deployment)
                    if state in deployment_copy['metadata']['name']:
                        YamlDeploymentStateless.remove(deployment)
                        YamlDeploymentStateful.remove(deployment)
                        try:
                            del deployment_copy['spec']['template']['spec']['containers'][0]['resources']
                        except:
                            pass
                        node_set = ['skv-node2', 'skv-node3', 'skv-node4', 'skv-node6', 'skv-node7']
                        if machine:
                            deployment_copy['spec']['template']['spec']['nodeName'] = node_set[random.randint(0, machine-1)]
                            # deployment_copy['spec']['template']['spec']['nodeName'] = 'skv-node2'
                        YamlDeploymentStateful.append(deployment_copy.copy())
                
                # 从YamlService搜索到本deployment对应的service进行修改，主要是修改选择器的标签值。
                # for service in YamlService.copy():
                #     if service['metadata']['labels'] == labels:
                #         YamlService.remove(service)
                #         for replica_th in range(replica_number):
                #             service_copy = copy.deepcopy(service)
                #             labels_copy = labels.copy()
                #             for label_key in labels_copy:
                #                 labels_copy[label_key] += '-' + str(replica_th)
                #             # service_copy['metadata']['labels'] = labels_copy.copy()
                #             # service_copy['metadata']['name'] += '-' + str(replica_th)
                #             YamlService.append(service_copy.copy())
                #         break
    with open(str(outPath) + MSname + '_YamlOthers.yaml', 'w') as f:
        yaml.dump_all(YamlOthers,  f)
    with open(str(outPath) + MSname + '_YamlDeploymentStateless.yaml', 'w') as f:
        yaml.dump_all(YamlDeploymentStateless,  f)
    with open(str(outPath) + MSname + '_YamlDeploymentStateful.yaml', 'w') as f:
        yaml.dump_all(YamlDeploymentStateful,  f)
    with open(str(outPath) + MSname + '_YamlService.yaml', 'w') as f:
        yaml.dump_all(YamlService,  f)


