import path_setup

import torch
import torchvision
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingWarmRestarts
import torchvision.transforms as transforms
import torch.nn as nn
from torchvision.models import resnet18
from accelerate import Accelerator

from hurricane.logger import Logger
from hurricane.utils import launch, log_all_configs
from configs import *
from resnet_trainer import ResNetTrainer


def main():
    
    logger_config = LoggerConfig()
    logger = Logger('train_resnet18_on_cifar10', **logger_config)
    log_all_configs(logger)
    
    accelerator_config = AcceleratorConfig()
    accelerator = Accelerator(**accelerator_config)
    
    transform = transforms.Compose(
        [
            transforms.ToTensor(),
            transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
        ]
    )

    with accelerator.main_process_first():

        dataset_config = DatasetConfig()
        dataset = torchvision.datasets.CIFAR10(
            transform=transform,
            **dataset_config,
        )

        model = resnet18(weights=None)
        model.fc = nn.Linear(model.fc.in_features, 10)

    data_loader_config = DataLoaderConfig()
    data_loader = torch.utils.data.DataLoader(
        dataset=dataset, 
        **data_loader_config,
    )
    
    optimizer_config = OptimizerConfig()
    optimizer = AdamW(
        params=model.parameters(), 
        **optimizer_config,
    )
    
    scheduler = CosineAnnealingWarmRestarts(
        optimizer=optimizer,
        T_0=len(data_loader) // accelerator_config.gradient_accumulation_steps,
    )
    
    trainer_config = TrainerConfig()
    trainer = ResNetTrainer(
        model=model,
        data_loader=data_loader,
        optimizer=optimizer,
        accelerator=accelerator,
        logger=logger,
        lr_scheduler=scheduler,
        lr_scheduler_mode='per_step',
        **trainer_config,
    )
    trainer.run()


if __name__ == '__main__':
    launch(main, num_processes=1, use_port="8000")
