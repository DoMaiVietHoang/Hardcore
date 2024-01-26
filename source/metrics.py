import torch
import torch.nn.functional as F
import numpy as np
import time
from metric_utils import *
def topk_accuracy(output, target, topk=(1,)):    
    """Computes the accuracy over the k top predictions for the specified values of k"""
    with torch.no_grad():       
        maxk = max(topk)
        batch_size = target.size(0)

        _, pred = output.topk(maxk, 1, True, True)
        pred = pred.t()
        correct = pred.eq(target.view(1, -1).expand_as(pred))

        res = []
        for k in topk:
            correct_k = correct[:k].reshape(-1).float().sum(0, keepdim=True)
            res.append(float(correct_k.mul_(100.0 / batch_size)))
        return res
    



def extract_labels(outputs, labels_obj, labels_count_arr, family_species_id, genus_species_id, rule='max'):
    t0 = time.time()
    num_rows = int(outputs.shape[0])
    outputs_np = outputs.cpu().detach().numpy()
    device = outputs.device
    l0, l1, l2 = labels_count_arr[-3:]
    
    if outputs.shape[1] == labels_count_arr[-1]:
        mat_species = outputs
        if rule == 'sum':
            mul_family =  build_mul_matrix(outputs_np, family_species_id)
            mul_genus =  build_mul_matrix(outputs_np, genus_species_id)
            mat_family = outputs@torch.tensor(mul_family).to(device)
            mat_genus = outputs@torch.tensor(mul_genus).to(device)
        if rule == 'max':
            t1 = time.time()
            max_family_idxs = torch.tensor(get_max_indices(outputs_np, family_species_id)).to(device)
            t2 = time.time()
            max_genus_idxs = torch.tensor(get_max_indices(outputs_np, genus_species_id)).to(device)
            t3 = time.time()
            
            mat_family = outputs.reshape(-1)[max_family_idxs.reshape(-1)].reshape(num_rows, -1)
            mat_genus = outputs.reshape(-1)[max_genus_idxs.reshape(-1)].reshape(num_rows, -1)
            t4 = time.time()
            # print ("extract_labels",rule,t4-t3, t3-t2, t2-t1, t1-t0)
        return [mat_family,mat_genus,mat_species]

    else:
        v0 = outputs[:,:l0]
        v1 = outputs[:,l0:l0+l1]
        v2 = outputs[:,l0+l1:l0+l1+l2]
        return [v0,v1,v2]

def extract_labels_slow(outputs, labels_obj, labels_count_arr, family_species_id, genus_species_id, rule='max'):
    if outputs.shape[1] == labels_count_arr[-1]:
        f_arr = []
        for f in family_species_id: 
            if rule == 'max':
                f_arr.append(outputs[:,f].max(dim=1).values)
            if rule == 'sum':
                f_arr.append(outputs[:,f].sum(dim=1))
                
        g_arr = []
        for g in genus_species_id: 
            if rule == 'max':
                g_arr.append(outputs[:,g].max(dim=1).values)
            if rule == 'sum':
                g_arr.append(outputs[:,g].sum(dim=1))
                
        # print (g_arr[0].shape)
        f_arr = torch.stack(f_arr, dim=1)
        g_arr = torch.stack(g_arr, dim=1)

        # print ("shape",f_arr.shape, g_arr.shape,f_arr)
        #print (t3-t2, t2-t1)
        return [f_arr,g_arr,outputs]
    else:
        l0 = len(family_species_id)
        l1 = len(genus_species_id)
        l3 = labels_count_arr[-1]

        v0 = outputs[:,:l0]
        v1 = outputs[:,l0:l0+l1]
        v2 = outputs[:,l0+l1:l0+l1+l3]
        return [v0,v1,v2]


class AverageMeter(object):
    """Computes and stores the average and current value.
       Code imported from https://github.com/pytorch/examples/blob/master/imagenet/main.py#L247-L262
    """
    def __init__(self):
        self.reset()

    def __init__(self, name, fmt=':f'):
        self.name = name
        self.fmt = fmt
        self.reset()

    def reset(self):
        self.val = 0
        self.avg = 0
        self.sum = 0
        self.count = 0
        self.arr = []

    def update(self, val, n=1):
        self.val = val
        self.arr.append(val)
        self.sum += val * n
        self.count += n
        self.avg = self.sum / self.count      

    def __str__(self):
        # fmtstr = '{name} {val' + self.fmt + '}({avg' + self.fmt + '})'
        fmtstr = '{name} {avg' + self.fmt + '}/{count}'
        
        return fmtstr.format(**self.__dict__)

    def __repr__(self):
        return self.__str__()