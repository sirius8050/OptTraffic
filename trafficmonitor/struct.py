
from typing import Dict, List, NewType


class Vertices:
    def __init__(self, Name: str, In: int, Out: int, SVC: str):
        self.Name = Name
        self.TotalTrafficIn = In
        self.TotalTrafficOut = Out
        self.IsMultiReplicas = False
        # Object
        self.Replicas = []
        # Resource
        self.CPU_request = 0
        self.CPU_used = 0
        self.RAM_request = 0
        self.RAM_used = 0
        # attribute
        self.MSName = None
        self.ServiceName = SVC
        self.NodeName = None
        # IP
        self.PodIP = None
        self.ServiceIP = None
        # 是否被插入监控组件
        self.insert = False
        # 是否为Stateful类型Pod
        self.Stateful = False

    def setReplicas(self, Replicas: list):
        self.IsMultiReplicas = True
        self.Replicas = Replicas


class Edge:
    def __init__(self, UM: Vertices, DM: Vertices, ratio: float):
        self.UM = UM
        self.DM = DM
        self.Name = UM.Name + '~' + DM.Name
        self.Send = 0
        self.Receive = 0
        self.Ratio = ratio
        self.IsMultiReplicas = False
        # Name:Object
        self.Replicas: List[Vertices] = []

    def setReplicas(self, Replicas: list):
        self.IsMultiReplicas = True
        self.Replicas = Replicas

    def setRatio(self, ratio: float):
        self.Ratio = ratio


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


class GraphSet:
    def __init__(self):
        self.GraphSet: Dict[str, Graph] = {}
        self.serviceEdge = None

    def addGraph(self, graph: Graph):
        self.GraphSet[graph.MSName] = graph
