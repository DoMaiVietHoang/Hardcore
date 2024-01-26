import torchvision
import torchvision.models as models

import torch.nn as nn
from torch.nn import *
import torch.nn.functional as F

class DenseNet169(nn.Module):
    def __init__(self, num_classes=1000, pretrained=True, softmax = False):
        super(DenseNet169, self).__init__()
        self.softmax = softmax
        weights='DenseNet169_Weights.DEFAULT'
        if not pretrained: weights = None
        self.model = torchvision.models.densenet169(weights=weights)
        self.model.classifier = Linear(in_features=1664, out_features=num_classes, bias=True)
        
    def forward(self,x):
        x = self.model(x)
        if self.softmax: x = F.softmax(x, dim=1) 
        return x