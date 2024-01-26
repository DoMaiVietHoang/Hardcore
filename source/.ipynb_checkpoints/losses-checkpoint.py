import time
import torch
import torch.nn as nn
from torch.nn import *
import torch.nn.functional as F
import torchvision
import torch.optim as optim
from torch.optim import lr_scheduler
import torch.backends.cudnn as cudnn
from torch.utils.data import Dataset, DataLoader

ce_loss = nn.CrossEntropyLoss()
cinna_weights = None

def calc_cinna_weights(hier_dict, labels_obj, device):
    family_dict,genus_dict,species_dict = hier_dict
    species = labels_obj.get_nodes('species')
    f_count = len(family_dict)
    g_count = len(genus_dict)
    s_count = len(species_dict)
    
    cls_count = f_count + g_count + s_count
    
    
    weights = torch.ones(cls_count,cls_count) * 0.
    for i,s in enumerate(species):
        g = s.parent
        f = g.parent
        f_id = family_dict[f]
        g_id = genus_dict[g]
        s_id = species_dict[s]
    
        c = 0
        mul = 1
        if True:
            mul/=2
            weights[i,c + f_id] = mul
            c += f_count
        if True:
            mul/=2
            weights[i,c + g_id] = mul
            c+=g_count
        c+=s_id
        weights[i,c] = mul
        # break
    return weights.to(device)

def cross_entropy_loss(pred, gt, *args):
    [vec0,vec1,vec2,labels] = gt
    device =  args[0]
    return ce_loss(pred, labels[:,-1].to(device))
    

def yolo_loss(pred, gt, *args):
    t0 = time.time()
    [vec0,vec1,vec2,labels] = gt
    l0 = vec0.shape[1]
    l1 = vec1.shape[1]
    l2 = vec2.shape[1]
    device =  args[0]
    labels_obj = args[1]
    hier_dict = args[2]
    family_genus_id, genus_species_id = args[3], args[4]
    # print ("family_genus_id",family_genus_id,genus_species_id)

    loss = 0
    #Family level
    vec = pred[:,:l0]
    loss += ce_loss(vec, labels[:,0].to(device))

    
    #apply softmax on all leaves of same node
    for i, arr in enumerate(family_genus_id):
        d_arr = {f:i for i,f in enumerate(arr)}
        # print ("d_arr",d_arr)
        if len(arr)>1:
            genus_vec = pred[:,l0:l0+l1]
            vec = genus_vec[:,arr]
            
            gt_vals = torch.zeros((vec.shape[0], len(arr)), dtype=torch.float32)
            exists = False
            for j in range(vec.shape[0]):
                g_id = int(labels[j,1])
                # print ("g_id",g_id, d_arr)
                if g_id in d_arr:
                    exists = True
                    index_g = d_arr[g_id]
                    gt_vals[j][index_g] = 1
            
            
            if exists:
                # print ("labels", labels[:,1],d_arr,gt_vals,vec)
                # print (vec,gt_vals)
                loss += ce_loss(vec, F.softmax(gt_vals.to(device),dim=1))

    for i, arr in enumerate(genus_species_id):
        d_arr = {f:i for i,f in enumerate(arr)}
        # print ("d_arr",d_arr)
        if len(arr)>1:
            species_vec = pred[:,l0+l1:]
            vec = species_vec[:,arr]
            gt_vals = torch.zeros((vec.shape[0], len(arr)), dtype=torch.float32)
            exists = False
            for j in range(vec.shape[0]):
                g_id = int(labels[j,1])
                # print ("g_id",g_id)
                if g_id in d_arr:
                    exists = True
                    index_g = d_arr[g_id]
                    gt_vals[j][index_g] = 1
            
            if exists:
                # print (vec,gt_vals)
                loss += ce_loss(vec, F.softmax(gt_vals.to(device),dim=1))

    loss += ce_loss(species_vec, labels[:,2].to(device))
    t1 = time.time()
    print ("time: ",t1-t0)
    return loss
    

def cinna_wu_loss(pred, gt, *args):
    global cinna_weights
    [vec0,vec1,vec2,labels] = gt
    l0 = vec0.shape[1]
    l1 = vec1.shape[1]
    l2 = vec2.shape[1]
    # print ("l0",l0,l1,l2, pred.shape)
    pred[:,:l0] = F.softmax(pred[:,:l0])
    pred[:,l0:l0+l1] = F.softmax(pred[:,l0:l0+l1])
    pred[:,l0+l1:] = F.softmax(pred[:,l0+l1:])
    
    device =  args[0]
    labels_obj = args[1]
    hier_dict = args[2]
    if cinna_weights is None: cinna_weights = calc_cinna_weights(hier_dict, labels_obj, device)
    # print (cinna_weights,cinna_weights.shape,cinna_weights[0])
    y_true_one_hot = torch.concatenate([vec0, vec1, vec2],dim=1).to(device)

    # Avoid numerical instability by adding a small value for numerical stability
    epsilon = 1e-9
    # print (y_pred.sum())
    pred = torch.clamp(pred, epsilon, 1.0 - epsilon)
    # print (y_pred.sum())
    #find the correct path in a tree
    # print (vec2)
    mul_mat2 = cinna_weights[labels[:,-1].to(device)]
    # print ("mul_mat2",mul_mat2.shape)

    # print (y_true_one_hot)
    # print (y_pred*mul_mat2)
    tmp = torch.clamp(pred*mul_mat2, epsilon, 1.0 - epsilon)
    # print (tmp)
    # print (torch.log(tmp))
    # print (y_true_one_hot * torch.log(tmp))
    return torch.sum(-y_true_one_hot * torch.log(tmp), axis=1).mean()
# loss = lecunn_func(outputs[:1],labels[:1],labels_num[:,-1].to(device))
# print (loss)
    

    

def tax_loss(pred, gt, *args):
    t0 = time.time()
    [vec0,vec1,vec2,labels] = gt
    l0 = vec0.shape[1]
    l1 = vec1.shape[1]
    l2 = vec2.shape[1]
    device =  args[0]
    labels_obj = args[1]
    hier_dict = args[2]
    family_genus_id, genus_species_id = args[3], args[4]
    outputs_family, outputs_genus, outputs_species = args[5], args[6], args[7]
    outputs_family =  F.softmax(outputs_family, dim=1)
    outputs_genus =  F.softmax(outputs_genus, dim=1)
    outputs_species =  F.softmax(outputs_species, dim=1)
    return ce_loss(outputs_family, labels[:,0].to(device)) + ce_loss(outputs_genus, labels[:,1].to(device)) +ce_loss(outputs_species, labels[:,2].to(device)) 

def adaptive_loss(pred, gt, *args):
    pass























































