import numpy as np
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
from tqdm import tqdm
from metrics import *

ce_loss = nn.CrossEntropyLoss()
cinna_weights = None
yolo_indices = None
rl = nn.ReLU()

def cross_entropy_loss_custom_factor(prob, labels, factor_vec):
    # Apply softmax to the logits
    prob = torch.softmax(prob, dim=1)
    
    # Compute the negative log probabilities for the true labels
    negative_log_probabilities = -torch.log(prob.gather(1, labels.unsqueeze(1)))
    
    # Compute the average loss
    loss = factor_vec*negative_log_probabilities
    
    return loss


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

def calc_ahl_weights(hier_dict, labels_obj, device):
    family_dict,genus_dict,species_dict = hier_dict
    species = labels_obj.get_nodes('species')
    f_count = len(family_dict)
    g_count = len(genus_dict)
    s_count = len(species_dict)
    
    cls_count = f_count + g_count + s_count
    
    
    weights_f = torch.ones(cls_count,cls_count) * 0.
    weights_g = torch.ones(cls_count,cls_count) * 0.
    weights_s = torch.ones(cls_count,cls_count) * 0.
    for i,s in enumerate(species):
        g = s.parent
        f = g.parent
        f_id = family_dict[f]
        g_id = genus_dict[g]
        s_id = species_dict[s]
    
        c = 0
        mul = 2
        if True:
            mul/=2
            weights_f[i,c + f_id] = 1
            c += f_count
        if True:
            mul/=2
            weights_g[i,c + g_id] = 1
            c+=g_count
        mul/=2
        c+=s_id
        weights_s[i,c] = 1
        # break
    return [weights_f.to(device),weights_g.to(device),weights_s.to(device)]

def cross_entropy_loss(pred, gt, *args):
    [vec0,vec1,vec2,labels] = gt
    device =  args[0]
    return ce_loss(pred, labels[:,-1].to(device))
    

def restore_pred_yolo(pred,gt, family_genus_id, genus_species_id ):
    [vec0,vec1,vec2,labels] = gt
    l0 = vec0.shape[1]
    l1 = vec1.shape[1]
    l2 = vec2.shape[1]

    for i,arr in enumerate(family_genus_id):
        arr2 = (np.array(arr) + l0).tolist()
        pred[:,arr2] *= pred[:, i].reshape(-1,1)

    for i,arr in enumerate(genus_species_id):
        arr2 = (np.array(arr) + l0 + l1).tolist()
        pred[:,arr2] *= pred[:, l0 + i].reshape(-1,1)

    return pred[:,:l0], pred[:,l0:l0+l1], pred[:, l0+l1:]
        
    
def yolo_loss(pred, gt, *args):
    global yolo_indices, gt_matrix
    def build_indices(family_genus_id, genus_species_id):
        indices = [] 
        c = len(family_genus_id)
        for arr in family_genus_id: indices.append( (np.array(arr) + c).tolist())
        c += len(genus_species_id)
        for arr in genus_species_id: indices.append( (np.array(arr) + c).tolist())
        return indices


    def build_gt_vector(rows, num_cls, vals):
        vec = torch.zeros(rows, num_cls)
        for i,v in enumerate(vals):
            vec[i,v] = 1
        return vec
        
        
    t0 = time.time()
    [vec0,vec1,vec2,labels] = gt
    l0 = vec0.shape[1]
    l1 = vec1.shape[1]
    l2 = vec2.shape[1]
    device =  args[0]
    labels_obj = args[1]
    hier_dict = args[2]
    family_genus_id, genus_species_id = args[3], args[4]
    
    if yolo_indices is None: yolo_indices = build_indices(family_genus_id, genus_species_id)
    
    t05 = time.time()
    rows = pred.shape[0]
    gt_matrix = torch.zeros((rows, l0+l1+l2))
    c = 0
    for i,(lbl_f, lbl_g, lbl_s) in enumerate(labels):
        gt_matrix[i, int(lbl_f)] = 1.
        gt_matrix[i, l0 + int(lbl_g)] = 1.
        gt_matrix[i, l0+ l1 +int(lbl_s)] = 1.
    
    t1 = time.time()
    # gt_matrix = torch.from_numpy(gt_matrix).to(device)
    
    family_prob = pred[:,:l0]
    family_gt = gt_matrix[:,:l0]
    loss = ce_loss(family_prob, family_gt.to(device))
    t2 = time.time()
    for i in range(l0):
        arr = yolo_indices[i]
        if len(arr)>1:
            family_genus_prob = pred[:,arr]
            family_genus_gt = gt_matrix[:,arr]
            c_loss = ce_loss(family_genus_prob, family_genus_gt.to(device))
            loss += c_loss

    for i in range(l1):
        arr = yolo_indices[l0+i]
        if len(arr)>1:
            genus_species_prob = pred[:,arr]
            genus_species_gt = gt_matrix[:,arr]
            c_loss = ce_loss(genus_species_prob, genus_species_gt.to(device))
            loss += c_loss
        
    
    # print (l0,l1,l2, pred.shape,loss, tmp)
    # print (family_prob[3], family_gt[3])
    t3 = time.time()
    # print ("time",t3-t2, t2-t1, t1-t05, t05-t0)
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

    # print (outputs_family.shape, outputs_genus.shape, outputs_species.shape)
    # l1 = cross_entropy_loss_custom(outputs_family, labels[:,0].to(device), softmax = True)
    # l2 = cross_entropy_loss_custom(outputs_genus, labels[:,1].to(device), softmax = True)
    # l3 = cross_entropy_loss_custom(outputs_species, labels[:,2].to(device), softmax = True) 

    l1 = ce_loss(outputs_family, labels[:,0].to(device))
    l2 = ce_loss(outputs_genus, labels[:,1].to(device))
    # print (outputs_species.max(), outputs_species.shape, labels[:,2].max(), labels[:,2].min() )
    l3 = ce_loss(outputs_species, labels[:,2].to(device))

    return l1 + l2 + l3

ahl_weights = None

def adaptive_loss(pred, gt, *args):
    #loss parent-child is cinna wu
    global ahl_weights
    t0 = time.time()
    [vec0,vec1,vec2,labels] = gt
    l0 = int(vec0.shape[1])
    l1 = int(vec1.shape[1])
    l2 = int(vec2.shape[1])
    device =  args[0]
    labels_obj = args[1]
    hier_dict = args[2]
    family_genus_id, genus_species_id = args[3], args[4]
    outputs_family, outputs_genus, outputs_species = args[5], args[6], args[7]
    family_species_id = args[8]

    weights_family, weights_peer = args[9], args[10]
    weights_family = F.softmax(weights_family)
    weights_peer = F.softmax(weights_peer)
    # print ("weights_family, weights_peer",weights_family, weights_peer)
    
    pred_len = l0 + l1 + l2

    if ahl_weights is None: ahl_weights = calc_ahl_weights(hier_dict, labels_obj, device)

    t1 = time.time()

     

    # l1_parent = ce_loss(outputs_family, labels[:,0].to(device))
    # l2_parent = ce_loss(outputs_genus, labels[:,1].to(device))
    l3_species = ce_loss(outputs_species, labels[:,2].to(device))

    # parent_child_loss = l1_parent * weights_family[0] + l2_parent * weights_family[1] + l3_species * weights_family[2]

    t2 = time.time()
    #peer loss
    if True:
        # print ("pred", pred.shape, l0,l1,l2)
        species_pred = pred[:,l0+l1:l0+l1+l2]
        outputs_family_peer, outputs_genus_peer, _ = extract_labels(species_pred, labels_obj, [l0,l1,l2], family_species_id, genus_species_id, 'sum')
       
        l1_peer = ce_loss(outputs_family_peer, labels[:,0].to(device))
        l2_peer = ce_loss(outputs_genus_peer, labels[:,1].to(device))
        
        peer_loss = l1_peer * weights_peer[0] + l2_peer * weights_peer[1] + l3_species * weights_peer[2]
    t3 = time.time()

    #adaptive cinna weights:

    pred[:,:l0] = F.softmax(pred[:,:l0])
    pred[:,l0:l0+l1] = F.softmax(pred[:,l0:l0+l1])
    pred[:,l0+l1:] = F.softmax(pred[:,l0+l1:])
    
    device =  args[0]
    labels_obj = args[1]
    hier_dict = args[2]
    y_true_one_hot = torch.concatenate([vec0, vec1, vec2],dim=1).to(device)
    epsilon = 1e-9

    wf_arr,wg_arr,ws_arr = ahl_weights[0],ahl_weights[1],ahl_weights[2]
    mul_mat1 = wf_arr[labels[:,-1].to(device)]
    mul_mat2 = wg_arr[labels[:,-1].to(device)]
    mul_mat3 = ws_arr[labels[:,-1].to(device)]
    mul_mat = mul_mat1*weights_family[0] + mul_mat2*weights_family[1] + mul_mat3*weights_family[2]
    tmp = torch.clamp(pred*mul_mat, epsilon, 1.0 - epsilon)
    # print (tmp)
    # print (torch.log(tmp))
    # print (y_true_one_hot * torch.log(tmp))
    parent_child_loss = torch.sum(-y_true_one_hot * torch.log(tmp), axis=1).mean()

    # print ("time",t3-t0, t3-t2,t2-t1,t1-t0)
        
    # return l3
    return l3_species + parent_child_loss + peer_loss
    # return l3_species + parent_child_loss + peer_loss ,factors , factors_peer


def adaptive_loss_ce_good(pred, gt, *args):
    t0 = time.time()
    [vec0,vec1,vec2,labels] = gt
    l0 = int(vec0.shape[1])
    l1 = int(vec1.shape[1])
    l2 = int(vec2.shape[1])
    device =  args[0]
    labels_obj = args[1]
    hier_dict = args[2]
    family_genus_id, genus_species_id = args[3], args[4]
    outputs_family, outputs_genus, outputs_species = args[5], args[6], args[7]
    family_species_id = args[8]

    weights_family, weights_peer = args[9], args[10]
    weights_family = F.softmax(weights_family)
    weights_peer = F.softmax(weights_peer)
    # print ("weights_family, weights_peer",weights_family, weights_peer)
    
    pred_len = l0 + l1 + l2


    t1 = time.time()

     

    l1_parent = ce_loss(outputs_family, labels[:,0].to(device))
    l2_parent = ce_loss(outputs_genus, labels[:,1].to(device))
    l3_species = ce_loss(outputs_species, labels[:,2].to(device))

    parent_child_loss = l1_parent * weights_family[0] + l2_parent * weights_family[1] + l3_species * weights_family[2]
    t2 = time.time()
    #peer loss
    if True:
        # print ("pred", pred.shape, l0,l1,l2)
        species_pred = pred[:,l0+l1:l0+l1+l2]
        outputs_family_peer, outputs_genus_peer, _ = extract_labels(species_pred, labels_obj, [l0,l1,l2], family_species_id, genus_species_id, 'sum')
       
        l1_peer = ce_loss(outputs_family_peer, labels[:,0].to(device))
        l2_peer = ce_loss(outputs_genus_peer, labels[:,1].to(device))
        
        peer_loss = l1_peer * weights_peer[0] + l2_peer * weights_peer[1] + l3_species * weights_peer[2]
    t3 = time.time()
    # print ("time",t3-t0, t3-t2,t2-t1,t1-t0)
        
    # return l3
    return l3_species + parent_child_loss + peer_loss
    # return l3_species + parent_child_loss + peer_loss ,factors , factors_peer


def adaptive_loss_per_factor(pred, gt, *args):
    t0 = time.time()
    [vec0,vec1,vec2,labels] = gt
    l0 = int(vec0.shape[1])
    l1 = int(vec1.shape[1])
    l2 = int(vec2.shape[1])
    device =  args[0]
    labels_obj = args[1]
    hier_dict = args[2]
    family_genus_id, genus_species_id = args[3], args[4]
    outputs_family, outputs_genus, outputs_species = args[5], args[6], args[7]
    family_species_id = args[8]
    
    pred_len = l0 + l1 + l2
    factors = pred[:,pred_len:pred_len+3]
    factors = rl(factors)

    l_species = ce_loss(outputs_species, labels[:,2].to(device))

    l1_parent = cross_entropy_loss_custom_factor(outputs_family, labels[:,0].to(device),factors[:,0])
    l2_parent = cross_entropy_loss_custom_factor(outputs_genus, labels[:,1].to(device),factors[:,1])
    l3_parent = cross_entropy_loss_custom_factor(outputs_species, labels[:,2].to(device),factors[:,2])

    parent_child_loss = torch.mean(l1_parent + l2_parent + l3_parent )
    #peer loss
    if True:
        # print ("pred", pred.shape, l0,l1,l2)
        species_pred = pred[:,l0+l1:l0+l1+l2]
        outputs_family_peer, outputs_genus_peer, _ = extract_labels(species_pred, labels_obj, [l0,l1,l2], family_species_id, genus_species_id, 'sum')
        factors_peer = pred[:,pred_len+3:pred_len+6]
        factors_peer = rl(factors_peer)

        l1_peer = cross_entropy_loss_custom_factor(outputs_family_peer, labels[:,0].to(device), factors_peer[:,0])
        l2_peer = cross_entropy_loss_custom_factor(outputs_genus_peer, labels[:,1].to(device), factors_peer[:,1])
        l3_peer = cross_entropy_loss_custom_factor(outputs_genus_peer, labels[:,1].to(device), factors_peer[:,2])
        
        peer_loss = torch.mean(l1_peer + l2_peer + l3_peer )
        
    # return l3
    return l_species + parent_child_loss +peer_loss, torch.mean(factors, dim=1) , torch.mean(factors_peer, dim=1)
    # return l3_species + parent_child_loss + peer_loss ,factors , factors_peer
    




def adaptive_loss_mul(pred, gt, *args):
    t0 = time.time()
    [vec0,vec1,vec2,labels] = gt
    l0 = int(vec0.shape[1])
    l1 = int(vec1.shape[1])
    l2 = int(vec2.shape[1])
    device =  args[0]
    labels_obj = args[1]
    hier_dict = args[2]
    family_genus_id, genus_species_id = args[3], args[4]
    outputs_family, outputs_genus, outputs_species = args[5], args[6], args[7]
    family_species_id = args[8]
    
    pred_len = l0 + l1 + l2
    factors = pred[:,pred_len:pred_len+3]
    # factors = torch.mean(F.softmax(factors, dim = 1), dim=1)

     
    l_species = ce_loss(outputs_species, labels[:,2].to(device))
    print("outputs_family",outputs_family.shape, factors.shape)
    l1_parent = ce_loss(outputs_family*factors[:,0], labels[:,0].to(device))
    l2_parent = ce_loss(outputs_genus*factors[:,1], labels[:,1].to(device))
    l3_species = ce_loss(outputs_species*factors[:,2], labels[:,2].to(device))

    parent_child_loss = l1_parent + l2_parent + l3_species 
    #peer loss
    if True:
        # print ("pred", pred.shape, l0,l1,l2)
        species_pred = pred[:,l0+l1:l0+l1+l2]
        outputs_family_peer, outputs_genus_peer, _ = extract_labels(species_pred, labels_obj, [l0,l1,l2], family_species_id, genus_species_id, 'sum')
        factors_peer = pred[:,pred_len+3:pred_len+6]
        # factors_peer = torch.mean(F.softmax(factors_peer, dim = 1), dim=1)

        l1_peer = ce_loss(outputs_family_peer*factors_peer[:,2], labels[:,0].to(device))
        l2_peer = ce_loss(outputs_genus_peer*factors_peer[:,2], labels[:,1].to(device))
        l3_peer = ce_loss(outputs_species*factors_peer[:,2], labels[:,1].to(device))
        
        peer_loss = l1_peer + l2_peer + l3_peer 
        
    # return l3
    return l_species + parent_child_loss +peer_loss ,factors , factors_peer
    # return l3_species + parent_child_loss + peer_loss ,factors , factors_peer



















































