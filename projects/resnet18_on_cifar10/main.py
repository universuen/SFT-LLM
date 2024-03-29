import _path_setup

import torch
import torchvision
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
import torchvision.transforms as transforms
import torch.nn as nn
from torchvision.models import resnet18
from accelerate import Accelerator

from hurricane.logger import Logger
from hurricane.utils import launch, log_all_configs
from configs.no_grad_accumulation import *
from resnet_trainer import ResNetTrainer


def main():
    logger = Logger(**LoggerConfig())
    log_all_configs(logger)
    accelerator = Accelerator(**AcceleratorConfig())
    transform = transforms.Compose(
        [
            transforms.ToTensor(),
            transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
        ]
    )
    with accelerator.main_process_first():
        dataset = torchvision.datasets.CIFAR10(
            transform=transform,
            **DatasetConfig(),
        )
        model = resnet18(weights=None)
        model.fc = nn.Linear(model.fc.in_features, 10)
    data_loader = torch.utils.data.DataLoader(
        dataset=dataset, 
        **DataLoaderConfig(),
    )
    optimizer = AdamW(
        params=model.parameters(), 
        **OptimizerConfig(),
    )
    scheduler = CosineAnnealingLR(
        optimizer=optimizer,
        T_max=(len(data_loader) // AcceleratorConfig().gradient_accumulation_steps) * TrainerConfig().epochs,
    )
    trainer = ResNetTrainer(
        model=model,
        data_loader=data_loader,
        optimizer=optimizer,
        accelerator=accelerator,
        logger=logger,
        lr_scheduler=scheduler,
        lr_scheduler_mode='per_step',
        **TrainerConfig(),
    )
    trainer.run()


if __name__ == '__main__':
    launch(main, num_processes=1, use_port="8002")
