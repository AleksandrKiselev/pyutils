import torch.nn as nn


class LinearModel(nn.Module):
    def __init__(self, input, output):
        super().__init__()
        self.linear_1 = nn.Linear(input, 128)
        self.linear_2 = nn.Linear(128, output)
        self.act = nn.ReLU()

    def forward(self, x):
        x = self.linear_1(x)
        x = self.act(x)
        x = self.linear_2(x)
        return x