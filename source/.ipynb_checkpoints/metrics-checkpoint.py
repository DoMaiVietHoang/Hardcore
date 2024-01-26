import torch 
import numpy as np

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
    
    if outputs.shape[1] == labels_count_arr[-1]:
        # original classes, compute parent by sum all the childs
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

        
        return [f_arr,g_arr,outputs]
    else:
        l0 = len(family_species_id)
        l1 = len(genus_species_id)

        v0 = outputs[:,:l0]
        v1 = outputs[:,l0:l0+l1]
        v2 = outputs[:,l0+l1:]
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