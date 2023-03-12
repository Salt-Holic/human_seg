import glob
import os

import numpy as np
import torch
from torch.utils.data.dataset import Dataset
import tqdm
import torch.nn as nn
import torch.nn.functional as F
import torch.quantization
import loss_func

import albumentations as A
from albumentations.pytorch.transforms import ToTensorV2
from torch.optim.adam import Adam
from torch.utils.data.dataloader import DataLoader
import cv2

from model import MobileUNet
import matplotlib.pyplot as plt
import segmentation_models_pytorch as smp


class Human(Dataset):
    def __init__(self, path_to_img, path_to_anno, train=True, transfrom=None):
        self.images = sorted(glob.glob(path_to_img + '/*.jpg'))
        self.annotations = sorted(glob.glob(path_to_anno + '/*.png'))

        self.X_train = self.images[:]
        self.Y_train = self.annotations[:]

        self.train = train
        self.transform = transfrom
        # self.input_size = input_size

    def __len__(self):
        if self.train:
            return len(self.X_train)
        # else:
        # return len(self.X_test)

    def preprocessing_mask(self, mask):
        # mask = mask.resize(self.input_size)
        # mask = np.resize(mask, self.input_size)
        # print(mask)
        mask[mask < 30] = 0
        mask[mask >= 30] = 1
        mask = mask.astype(np.float32)

        # cv2.convertScaleAbs(mask)
        # cv2.imshow(' ', mask)
        # cv2.waitKey(0)
        # cv2.destroyAllWindows()
        mask = self.transform(image=mask)['image']

        # mask[mask < 255] = 0
        # mask[mask == 255.0] = 1

        # mask = torch.tensor(mask)
        # mask = mask.squeeze()
        return mask

    def __getitem__(self, i):
        X_train = cv2.imread(self.X_train[i])
        # cv2.imshow('', X_train)
        X_train = X_train.astype(np.float32)
        X_train = self.transform(image=X_train)['image']
        # X_train = torch.tensor(X_train)

        Y_train = cv2.imread(self.Y_train[i], cv2.IMREAD_GRAYSCALE)
        Y_train = self.preprocessing_mask(Y_train)

        return X_train, Y_train


device = 'cuda' if torch.cuda.is_available() else 'cpu'

transform = A.Compose([
    A.Resize(width=256, height=256),
    A.HorizontalFlip(),
    A.Rotate(limit=20),
    ToTensorV2()
])

train_set = Human(path_to_img='D:seg_resize2/image/',
                  path_to_anno='D:seg_resize2/mask/',
                  transfrom=transform,
                  )

train_loader = DataLoader(train_set, batch_size=64, shuffle=True)

# model = MobileUNet().to(device)
model = smp.Unet(
    encoder_name='timm-mobilenetv3_small_minimal_100',
    encoder_weights='imagenet',
    in_channels=3,
    classes=1
)
model = model.cuda()
# model = torch.quantization.quantize_dynamic(model, {nn.Conv2d}, dtype=torch.qint8)

lr = 0.0001

optim = Adam(params=model.parameters(), lr=lr)

dice = loss_func.DiceBCELoss()
focal = loss_func.FocalLoss()

# 가중치만 불러오기
# model.load_state_dict(torch.load('./mobilenet_v2-7ebf99e0.pth'), strict=False)

# load checkpoint
# checkpoint = torch.load('D:fix_mask/Portrait_seg_15.pth')
# model.load_state_dict(checkpoint['model_state_dict'])
# optim.load_state_dict(checkpoint['optimizer_state_dict'])
# num_epoch = checkpoint['epoch']

best_loss = 9999

# train
for epoch in range(200):
    iterator = tqdm.tqdm(train_loader)
    running_loss = 0.0
    for data, label in iterator:
        optim.zero_grad()

        preds = model(data.to(device))
        loss = nn.BCEWithLogitsLoss()(preds, label.type(torch.FloatTensor).to(device))
        # loss = dice(preds, label.type(torch.FloatTensor).to(device))
        # loss = focal(preds, label.type(torch.FloatTensor).to(device))

        loss.backward()
        optim.step()

        running_loss += loss.item()

        iterator.set_description(f'epoch: {epoch + 1} loss: {loss.item()}')
    print('Train Loss:', running_loss / len(train_loader))

    # save checkpoint
    if (epoch + 1) % 5 == 0:
        torch.save({
            'model_state_dict': model.state_dict(),
            'optimizer_state_dict': optim.state_dict(),
            'epoch': epoch
        }, f'D:/BCE/BCE_loss_Aug{epoch + 1}.pth')

    if best_loss > running_loss / len(train_loader):
        best_loss = running_loss / len(train_loader)

        torch.save({
            'model_state_dict': model.state_dict(),
            'optimizer_state_dict': optim.state_dict(),
            'epoch': epoch
        }, f'D:/BCE/Best_BCE_Loss_Aug.pth')

torch.save({
    'model_state_dict': model.state_dict(),
    'optimizer_state_dict': optim.state_dict(),
    'epoch': 200
}, 'Portrait_segmentation.pth')
