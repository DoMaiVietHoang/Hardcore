import argparse
from re import split
import shutil
import os
import matplotlib.pyplot as plt
from datasets import *
from models import *
import torch
from torch.utils.data import Dataset, DataLoader
import torchvision.transforms as transforms
import json
from tqdm import tqdm
from metrics import *
import torch.nn as nn
from torch.nn import *
import torch.nn.functional as F
import torchvision
import torch.optim as optim
from torch.optim import lr_scheduler
import torch.backends.cudnn as cudnn
from torch.utils.data import Dataset, DataLoader
from losses import *

dirs = [
    '/home/namhv2/plantclef2015/',
    '/home/namhv2/plantclef2017/',
    'D:/Hoang/Plant Identify/mapr/data/phutho/',
]
WANDB_KEY = 'xxxxxxxxxxxxxxxxxxxxxxxxxx'

parser = argparse.ArgumentParser(description='Training params')
parser.add_argument('--name', type=str, default='AdaptiveLoss', help='project name for saving/logging to wandb')
parser.add_argument('--prefix', type=str, default='', help='run name prefix')
parser.add_argument('--dataset', type=str, default='phutho', help='dataset to use, choices: plantnet2015, plantnet2017, phutho')
parser.add_argument('--loss', type=str, default='cross_entropy', help='loss function, choices: cross_entropy, tax_loss, yolo, cinna_wu, adaptive')
parser.add_argument('--model', type=str, default='resnet50', help='deep learning model, choices: resnet50, densenet169, senet154,senext50, transformerb16')
parser.add_argument('--epoch', type=int, default=100, help='Number of epochs')
parser.add_argument('--step', type=int, default=10, help='Number of epochs for LRStep, 0: disable')
parser.add_argument('--batch_size', type=int, default=32, help='batch size')
parser.add_argument('--gpu', type=int, default=0, help='GPU ID (only 1), -1: cpu')
parser.add_argument('--lr', type=float, default=.001, help='initial Learning Rate')
parser.add_argument('--optim', type=str, default='sgd', help='optimizers, choices: sgd, adam, aldelta')
parser.add_argument('--wandb', type=bool, default=False, help='logging to Wandb')
parser.add_argument('--worker', type=int, default=0, help='num workers')
parser.add_argument('--early_stop', type=int, default=0, help='early stopping epochs, 0: disable')
parser.add_argument('--rule', type=str, default='auto', help='spliting rule for getting higher level probs from its child, choices: auto, max, sum')

args = parser.parse_args()
args_dict = vars(args)
config = args_dict
print("\n=========CONFIG=============\n", args_dict)

os.environ["CUDA_DEVICE_ORDER"]="PCI_BUS_ID"   # see issue #152
os.environ["CUDA_VISIBLE_DEVICES"]=str(args.gpu)
os.environ['WANDB_API_KEY']=WANDB_KEY

name = args.name
dataset = args.dataset
loss_type = args.loss
model_type = args.model
num_epochs = args.epoch
step_size = args.step
batch_size = args.batch_size
gpu = args.gpu
lr = args.lr
optim_type = args.optim
use_wandb = args.wandb
worker = args.worker
early_stop = args.early_stop
prefix = args.prefix
rule = args.rule

outdir = f"results/{dataset}/{model_type}/{loss_type}/"
run_name = f"{prefix}{model_type}_{loss_type}"
if not os.path.exists(outdir): os.makedirs(outdir)

transform =  transforms.Compose([
            # transforms.RandomAffine(0, translate=(0.2, 0.2), scale=(0.8, 1.5)),
            transforms.RandomRotation(degrees=(-90, 90)),
            transforms.Resize((224, 224)),
            # transforms.RandomApply([transforms.ColorJitter(brightness=0.1, contrast=0.1, saturation=0.1, hue=0.1)], p=0.8),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])  # Normalize the image

        ])

print ("\n==Loading data==")
if dataset == 'plantnet2015':
    pass
if dataset == 'plantnet2017':
    train_dataset = PlantClef2017Dataset(dirs[1], transform = transform, mode = 'train')
    test_dataset = PlantClef2017Dataset(dirs[1], transform = None, mode = 'test')

    
if dataset == 'phutho':
    train_dataset = PhuThoDataset(dirs[2], transform = transform, mode = 'train')
    test_dataset = PhuThoDataset(dirs[2], transform = None, mode = 'test')

labels_obj = train_dataset.labels_obj
hier_dict = train_dataset.hier_dict
family_species_id, family_genus_id, genus_species_id = train_dataset.family_species_id, train_dataset.family_genus_id, train_dataset.genus_species_id 
labels_count_arr = train_dataset.labels_obj.get_cls_count()


# CLASS NUMBERS
n_class = labels_count_arr[-1]
if loss_type in ['yolo', 'cinna_wu']: n_class += labels_count_arr[-2] + labels_count_arr[-3]
if loss_type == 'adaptive': 
    n_class += labels_count_arr[-2] + labels_count_arr[-3] 

################################################################
#PYTORCH Part


if gpu == -1: device = torch.device("cpu")
else: device = torch.device("cuda:0")

wandb_created = False

# LOSS FUNCTION
split_rule = 'max'
if loss_type == 'cross_entropy': criterion = cross_entropy_loss
if loss_type == 'yolo': criterion = yolo_loss
if loss_type == 'cinna_wu': criterion = cinna_wu_loss
if loss_type == 'tax_loss':
    criterion = tax_loss
    # split_rule = 'sum'
softmax = False
if rule != 'auto':
    split_rule = rule
    
trainloader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=worker,pin_memory=True)
testloader  = DataLoader(test_dataset, batch_size=batch_size, shuffle=False, num_workers=worker,pin_memory=True)
print ("trainloader",trainloader.num_workers)
print (f"\n== Creating model {model_type}==")
if model_type == 'resnet50': model = Resnet50(n_class, softmax = softmax, pretrained = True)
if model_type == 'densenet169': model = DenseNet169(n_class, softmax = softmax, pretrained = True)
if model_type == 'senet154': model = SeNet154(n_class, softmax = softmax, pretrained = True)
if model_type == 'senext50': model = SeResNext50(n_class, softmax = softmax, pretrained = True)
if model_type == 'transformerb16': model = VisionTransformer(n_class, softmax = softmax, pretrained = True)



if loss_type == 'adaptive': 
    criterion = adaptive_loss
model.weights_family = nn.Parameter(torch.tensor([2.,2.,10.]))
model.weights_peer = nn.Parameter(torch.tensor([2.,2.,10.]))
model.weights_family.requires_grad = False
model.weights_peer.requires_grad = False
# print ("haha model.weights_peer",model.weights_peer,model.weights_peer.requires_grad)


print("Model size: {:.5f}M".format(sum(p.numel() for p in model.parameters())/1000000.0))

params_to_update = model.parameters()
if optim_type.lower() == 'sgd': optimizer = optim.SGD(params_to_update, lr=lr, momentum=0.9,weight_decay=5e-04)
if optim_type.lower() == 'aldelta': optimizer = optim.Adadelta(params_to_update)
if optim_type.lower() == 'adam': optimizer = optim.Adam(params_to_update)

if step_size > 0:
    scheduler = lr_scheduler.StepLR(optimizer, step_size=step_size, gamma=0.1)

    # softmax = True
model = model.to(device)
wandb_created = False
best_acc = 0
print (f"\n==Training model==")
# print ("model.weights_family",model.weights_family)
for epoch in range(0,num_epochs):
    log_path = f'{outdir}/log_{str(epoch).zfill(4)}.json'
    top1 = AverageMeter('Acc@1', ':6.3f')
    top1_f = AverageMeter('Acc@1', ':6.3f')
    top1_g = AverageMeter('Acc@1', ':6.3f')

    top1_train = AverageMeter('Acc@1', ':6.3f')
    top5 = AverageMeter('Acc@5', ':6.3f')
    top5_f = AverageMeter('Acc@5', ':6.3f')
    top5_g = AverageMeter('Acc@5', ':6.3f')
    top10 = AverageMeter('Acc@10', ':6.3f')
    top10_f = AverageMeter('Acc@10', ':6.3f')
    top10_g = AverageMeter('Acc@10', ':6.3f')
    train_loss = AverageMeter('TrainLoss', ':.4e')
    val_loss = AverageMeter('ValLoss', ':.4e')
    print (epoch,'/',num_epochs,best_acc)
    log_obj = {}

    acc_arr = []
    
    if loss_type == 'adaptive' and epoch == 9:
        model.weights_family.requires_grad = True
        model.weights_peer.requires_grad = True
    
    for i,data in tqdm(enumerate(trainloader)):
        t0 = time.time()
        images,vec0,vec1,vec2,labels_cpu = data
        images = images.to(device)
        labels = labels_cpu.to(device)

        optimizer.zero_grad()
        outputs = model(images)


        # if loss_type == 'tax_loss': outputs = F.softmax(outputs,dim=1)
        # if loss_type == 'cross_entropy': outputs = F.softmax(outputs,dim=1)
        # print (outputs.shape)

        
        t1 = time.time()
        # print ("extract labels", split_rule)
        outputs_family, outputs_genus, outputs_species = extract_labels(outputs, labels_obj, labels_count_arr, family_species_id, genus_species_id, split_rule) 
        t2 = time.time()
        # print (labels.dtype)
        # print (outputs_family[0],outputs_family[0].sum())
        # print (outputs_genus[0],outputs_genus[0].sum())
        # print (outputs_species[0],outputs_species[0].sum())
        # break
        # print (outputs_species, labels[:,-1])
        loss = criterion(outputs,[vec0,vec1,vec2,labels], device, labels_obj, hier_dict, family_genus_id, genus_species_id, outputs_family, outputs_genus, outputs_species, family_species_id, model.weights_family, model.weights_peer)
        t3 = time.time()
        if loss_type == 'yolo': 
            outputs_family, outputs_genus, outputs_species = restore_pred_yolo(outputs,[vec0,vec1,vec2,labels],family_genus_id, genus_species_id)
        if loss_type == 'adaptive':
            l0, l1, l2 = labels_count_arr[-3:]
            species_pred = outputs[:,l0+l1:l0+l1+l2]
            outputs_family, outputs_genus, _ = extract_labels(species_pred, labels_obj, labels_count_arr, family_species_id, genus_species_id, split_rule)
        t4 = time.time()
        # print (outputs_family.shape, outputs_genus.shape, outputs_species.shape)
        acc1, acc5,acc10 = topk_accuracy(outputs_species.detach().cpu(), labels[:,2].detach().cpu(), (1,5,10))
        t5 = time.time()
        top1_train.update(acc1, images.size(0))
        train_loss.update(float(loss), images.size(0))
        # model.weights_family.retain_grad()
        # model.weights_peer.retain_grad()
        loss.backward()
        optimizer.step()
        t6 = time.time()
        # with torch.no_grad():
        #   if loss_type == 'adaptive':
        #       # print ("gradient:",model.weights_family.grad,model.weights_peer.grad, model.weights_family)
        #       #print ("current weights family",model.weights_family,model.weights_peer) 
        #       weights_sum = model.weights_family.sum()
        #       model.weights_family = model.weights_family.div_(weights_sum)
        #       weights_sum = model.weights_peer.sum()
        #       model.weights_peer = model.weights_peer.div_(weights_sum)
        # if i>=2: break
        if epoch == 0 and i%100==0:
            print (f"Train loss: {train_loss.avg}")
            # print ("weights:",model.weights_family,model.weights_peer)
            # print ("time: ",t6-t5, t5-t4, t4-t3, t3-t2, t2-t1,t1-t0)
        # break
    if step_size > 0: scheduler.step()

    # break

    # print ("weights:",model.weights_family,model.weights_peer)
    
    model.eval()

    with torch.no_grad():
        for i,data in tqdm(enumerate(testloader)):
            images,vec0,vec1,vec2,labels_cpu = data
            images = images.to(device)
            labels = labels_cpu.to(device)
            outputs = model(images)
            # if loss_type == 'tax_loss': outputs = F.softmax(outputs,dim=1)
            # print (outputs.shape)
            _, predicted = torch.max(outputs.data, 1)
            
            # loss = criterion(output_lecunn, labels_num[:,-1].to(device))
            
            outputs_family, outputs_genus, outputs_species = extract_labels(outputs, labels_obj, labels_count_arr, family_species_id, genus_species_id, split_rule) 
            loss = criterion(outputs,[vec0,vec1,vec2,labels], device, labels_obj, hier_dict, family_genus_id, genus_species_id, outputs_family, outputs_genus, outputs_species, family_species_id, model.weights_family, model.weights_peer)
            weights_family_prob = F.softmax(model.weights_family)
            weights_peer_prob = F.softmax(model.weights_peer)
            
            log_obj['w_family_parent'] = float(weights_family_prob[0])
            log_obj['w_genus_parent'] = float(weights_family_prob[1])
            log_obj['w_species_parent'] = float(weights_family_prob[2])
            log_obj['w_family_peer'] = float(weights_peer_prob[0])
            log_obj['w_genus_peer'] = float(weights_peer_prob[1])
            log_obj['w_species_peer'] = float(weights_peer_prob[2])
            if loss_type == 'yolo': 
                outputs_family, outputs_genus, outputs_species = restore_pred_yolo(outputs,[vec0,vec1,vec2,labels],family_genus_id, genus_species_id)
            if loss_type == 'adaptive':
                l0, l1, l2 = labels_count_arr[-3:]
                species_pred = outputs[:,l0+l1:l0+l1+l2]
                outputs_family, outputs_genus, _ = extract_labels(species_pred, labels_obj, labels_count_arr, family_species_id, genus_species_id, split_rule)
            acc1, acc5,acc10 = topk_accuracy(outputs_species.detach().cpu(), labels[:,2].detach().cpu(), (1,5,10))
            top1.update(acc1, images.size(0))
            top5.update(acc5, images.size(0))
            top10.update(acc10, images.size(0))

            acc1, acc5,acc10 = topk_accuracy(outputs_family.detach().cpu(), labels[:,0].detach().cpu(), (1,5,10))
            top1_f.update(acc1, images.size(0))
            top5_f.update(acc5, images.size(0))
            top10_f.update(acc10, images.size(0))

            acc1, acc5,acc10 = topk_accuracy(outputs_genus.detach().cpu(), labels[:,1].detach().cpu(), (1,5,10))
            top1_g.update(acc1, images.size(0))
            top5_g.update(acc5, images.size(0))
            top10_g.update(acc10, images.size(0))
            
            val_loss.update(float(loss), images.size(0))
    # break
    log_obj['train_loss'] = train_loss.avg
    log_obj['val_loss'] = val_loss.avg
    log_obj['top1_s_acc'] = top1.avg
    log_obj['top5_s_acc'] = top5.avg
    log_obj['top10_s_acc'] = top10.avg
    log_obj['top1_g_acc'] = top1_g.avg
    log_obj['top5_g_acc'] = top5_g.avg
    log_obj['top10_g_acc'] = top10_g.avg
    log_obj['top1_f_acc'] = top1_f.avg
    log_obj['top5_f_acc'] = top5_f.avg
    log_obj['top10_f_acc'] = top10_f.avg
    log_obj['train_acc'] = top1_train.avg
    #log_obj['max_v'] = [top1_f.max(), top1_g.max(), top1.max(), top5.max(), top10.max()]
    acc_arr.append(top1.avg)
    log_obj2 = log_obj
    json.dump(log_obj2, open(log_path,'wt'))
    save = False
    is_best = False
    if top1.avg > best_acc:
        best_acc = top1.avg
        save = True
        is_best = True
    if epoch%10 == 0:
        save = True
    if save:
        path = f'{outdir}/last.pth'
        if is_best:
            path = f'{outdir}/best.pth'
        torch.save(model.state_dict(), path)

    if use_wandb:
        if not wandb_created:
            print (f"\n==Initializing wandb==")
            import wandb
            wandb.init(project=name,
                config=config)
            wandb.run.name = run_name
            wandb.run.save()
            wandb_created = True
        wandb.log(log_obj)

    if early_stop != 0:
        l = len(acc_arr)
        if l>early_stop:
            best_acc = max(acc_arr)
            id = acc_arr.index(best_acc)
            if l-id > early_stop: 
                print ("-------------Early stopping is activated !")
                break
            
            




























































































































































































































