def add_if_not_exists(obj, d):
    if obj not in d:
        d[obj] = len(d)
    return d[obj]

class Node:
    def __init__(self, name, type=None, id=None, index = -1):
        self.name = name
        self.id = id
        self.parent = None
        self.type = type
        self.childs = {}
        self.index = index
        self.attributes = {}
        self.level = -1
    def check(self,name, type, id):
        return self.name == name and self.type==type and self.id == id
    def get_childs(self): return list(self.childs.values())
    def __repr__(self):
        return self.__str__()
    def __str__(self):
        return f"[{self.type.upper()}] {self.name}"
    def add_child(self, node):
        self.childs[node.name] = node
    def get_num_leaf(self):
        if len(self.childs) == 0: return 1
        c = 0
        for k,node in self.childs.items():
            c += node.get_num_leaf()
        return c
    
    def set(self,k,v):
        self.attributes[k] = v
    
    def get(self, k, default=None):
        if k in self.attributes: return self.attributes[k]
        return default

class LabelsTree:
    def __init__(self):
        self.nodes = {}
        self.types = {}
        self.height = 0
        self.type_index_dict = {} #store index of nodes
        
    def add_node(self, name, type, id):
        self.types[type] = 0
        new = False
        k = f"{type}-{name}-{id}"
        if k not in self.nodes:
            # if type not in self.type_index_dict:
            #     self.type_index_dict[type] = 0
            # idx = self.type_index_dict[type]
            # self.type_index_dict[type] +=1 
            node = Node(name,type, id)
            self.nodes[k] = node
            new = True
        return self.nodes[k], new
        
    def add_label(self, node_arr, update=True):
        last_node = None
        for name,type,id in node_arr:
            node, is_new = self.add_node(name,type,id)
            if is_new:
                obj = self.type_index_dict
                if type not in self.type_index_dict: obj[type] = {}
                obj[type][node] = len(obj[type])
                if last_node is not None:
                    last_node.add_child(node)
                    node.parent = last_node
            last_node=node
        if update:
            self.update_tree()
    def get_nodes(self, type):
        arr = []
        for k,node in self.nodes.items():
            if node.type == type: arr.append(node)
        return arr


    def update_tree(self):
        for i in range(10):
            exists = False
            for k,node in self.nodes.items():
                if i == 0:
                    if node.parent is None:
                        node.level = 0
                        exists = True
                else:
                    if node.parent is not None and node.parent.level == i-1:
                        node.level = i
                        exists = True
            if not exists: 
                self.height = i
                break

    def get_level(self, level):
        arr = []
        for k,node in self.nodes.items():
            if node.level == level: arr.append(node)
        return arr

    def get_cls_count(self):
        arr = []
        for i in range(self.height):
            arr.append(len(self.get_level(i)))
        return arr

