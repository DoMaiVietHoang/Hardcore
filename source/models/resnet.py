import torchvision
import torchvision.models as models

import torch.nn as nn
from torch.nn import *
import torch.nn.functional as F

class Resnet50(nn.Module):
    def __init__(self, num_classes=1000, pretrained=True, softmax = False):
        super(Resnet50, self).__init__()
        self.softmax = softmax
        weights='ResNet50_Weights.DEFAULT'
        if not pretrained: weights = None
        self.resnet = torchvision.models.resnet50(weights=weights)
        self.resnet.fc = Linear(in_features=2048, out_features=num_classes, bias=True)
        
    def forward(self,x):
        x = self.resnet(x)
        if self.softmax: x = F.softmax(x, dim=1) 
        return x