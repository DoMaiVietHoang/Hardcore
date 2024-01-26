from .utils import *
import json
import numpy as np
import os
from PIL import Image
import pickle as pkl
from tqdm import tqdm
import torch
from torch.utils.data import Dataset
import torchvision.transforms as transforms
from labels_tree import LabelsTree

__all__ = ['PhuThoDataset']
name = "PhuThoDataset"


mean = [0.485, 0.456, 0.406]
std = [0.229, 0.224, 0.225]

def get_paths(indir):
    arr = []
    for root,_,files in os.walk(indir):
        for f in files:
            path = root + '/' +f
            s = os.path.getsize(path)
            ext = f.split('.')[-1].lower()
            if ext in ['jpg','jpeg','png'] and s > 1000:
                arr.append(root+'/'+f)
    return arr

def parsing_files(indir, mode = 'train'):
    if not os.path.exists('data'): os.makedirs('data')
    label_obj_path = f'data/data_{name}.pkl'
    if os.path.exists(label_obj_path):
        labels_obj = pkl.load(open(label_obj_path, 'rb'))
    else:
        gt = json.load(open(indir+'/classes_tree.json'))
        labels_obj = LabelsTree()
        for o,f,g,s,id in gt:
            labels_obj.add_label([
                [o,'order',None],
                [f,'family',None],
                [g,'genus',None],
                [s,'species',id],
                ])
        
        # Read train/test paths
        all_paths = get_paths(indir+'/AI/')
        # test_paths = get_paths(indir+'/test')
    
        test_names = {}
        lines = open(indir+'/test.txt').read().strip().split('\n')
        for l in lines:
            l = l.strip().split('/')[-1].split()[0]
            test_names[l] = 0
        
        # # assign paths for each class
        train_dict = {}
        test_dict = {}
        train_count = 0
        test_count = 0
        for path in all_paths:
            n = path.split('/')[-1]
            id = path.split('/')[-2]
            if n in test_names:
                if id not in test_dict: test_dict[id] = []    
                test_dict[id].append(path)
            else:
                if id not in train_dict: train_dict[id] = []
                train_dict[id].append(path)
        
        species_obj = labels_obj.get_nodes('species')
        for s in species_obj:
            # paths = train_dict[s.id]
            s.set('train_paths', train_dict[s.id])
            s.set('test_paths', test_dict[s.id])
        # # save object
        pkl.dump(labels_obj, open(label_obj_path, 'wb'))

    species_obj = labels_obj.get_nodes('species')
    family_dict,genus_dict, species_dict = {}, {}, {}
    for s in labels_obj.get_nodes('family'): family_dict[s] = len(family_dict)
    for s in labels_obj.get_nodes('genus'): genus_dict[s] = len(genus_dict)
    for s in labels_obj.get_nodes('species'): species_dict[s] = len(species_dict)

    hier_dict = [family_dict,genus_dict, species_dict]
    family_species_id = []
    family_genus_id = []
    genus_species_id = []
    for f in labels_obj.get_nodes('family'):
        childs = f.get_childs()
        arr0 = []
        arr = []
        for c in childs:
            s_arr = c.get_childs()
            for s in s_arr:
                arr.append(species_dict[s])
            arr0.append(genus_dict[c])
        family_species_id.append(arr)
        family_genus_id.append(arr0)
    for s in labels_obj.get_nodes('genus'):
        childs = s.get_childs()
        arr = []
        for s in childs:
            arr.append(species_dict[s])
        genus_species_id.append(arr)
    
    train_data, test_data = [], []
    for s in species_obj:
        vec0, vec1, vec2, labels = get_one_hot_label(s, family_dict,genus_dict, species_dict)
        paths = []
        for p in s.get('train_paths'):
            paths.append([p,vec0, vec1, vec2,labels])
        train_data.extend(paths)
        paths = []
        for p in s.get('test_paths'):
            paths.append([p,vec0, vec1, vec2,labels])
        test_data.extend(paths)

    data = train_data
    if mode == 'test': data = test_data
    return data, labels_obj,hier_dict, family_species_id,family_genus_id, genus_species_id

def get_one_hot_label(node, family_dict,genus_dict, species_dict):
    labels_num = []
    
    idf = family_dict[node.parent.parent]
    labels_num.append(idf)
    vec0 = [0.]*len(family_dict)
    vec0[idf] = 1.
    
    idf = genus_dict[node.parent]
    labels_num.append(idf)
    vec1 = [0.]*len(genus_dict)
    vec1[idf] = 1.
    
    vec2 = [0.]*len(species_dict)
    idf = species_dict[node]
    labels_num.append(idf)
    vec2[idf] = 1.
    return np.array(vec0),np.array(vec1),np.array(vec2), np.array(labels_num)


class PhuThoDataset(Dataset):
    def __init__(self, directory, transform = None, mode='train'):
        self.transform = transform
        if transform is None:
            self.transform = transforms.Compose([
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(mean=mean, std=std)
            ])

        
        self.data, self.labels_obj, self.hier_dict, self.family_species_id, self.family_genus_id, self.genus_species_id = parsing_files(directory, mode)
        print (f"Phutho {mode} {len(self.data)} images")

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        path, vec0, vec1, vec2, labels = self.data[idx]
        image = Image.open(path).convert('RGB')
        image = self.transform(image)
#         image = image.permute(1, 2, 0)
       
        vec0 = torch.from_numpy(vec0)
        vec1 = torch.from_numpy(vec1)
        vec2 = torch.from_numpy(vec2)
        labels = torch.from_numpy(labels)
        return image,vec0,vec1,vec2,labels

    def convert(self,images):
        reverse_normalize = transforms.Normalize((-mean[0] / std[0], -mean[1] / std[1], -mean[2] / std[2]), (1.0 / std[0], 1.0 / std[1], 1.0 / std[2]))
        images =  reverse_normalize(images)
        images = torch.swapaxes(images, 3, 1)
        images = torch.swapaxes(images, 1, 2)
        return images


