import torchvision
import torchvision.models as models

import torch.nn as nn
from torch.nn import *
import torch.nn.functional as F

class VisionTransformer(nn.Module):
    def __init__(self, num_classes=1000, pretrained=True, softmax = False):
        super(VisionTransformer, self).__init__()
        self.softmax = softmax
        weights='ViT_B_16_Weights.DEFAULT'
        if not pretrained: weights = None
        self.model = torchvision.models.vit_b_16(weights=weights)
        # self.model.head = Linear(in_features=1200, out_features=num_classes, bias=True)
        self.model.heads.head = Linear(in_features=768, out_features=num_classes, bias=True)
        
    def forward(self,x):
        x = self.model(x)
        if self.softmax: x = F.softmax(x, dim=1) 
        return x