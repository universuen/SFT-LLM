import _path_setup

import os

from torch.utils.data import DataLoader
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from transformers import AutoTokenizer, AutoModelForCausalLM
from accelerate import Accelerator

from hurricane.trainers import HFLLMTrainer
from hurricane.collators import HFLLMITCollator
from hurricane.utils import Logger, launch, log_all_configs

from zhihu_qa_dataset import ZhihuQADataset
from configs.opt_350m import (
    LoggerConfig,
    AcceleratorConfig,
    DataLoaderConfig,
    OptimizerConfig,
    TrainerConfig,
    LaunchConfig,
    CollatorConfig,
    model_name,
)


def main():
    accelerator = Accelerator(**AcceleratorConfig())
    logger = Logger(**LoggerConfig())
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    if accelerator.is_main_process:
        log_all_configs(logger)
        logger.info('Set TOKENIZERS_PARALLELISM=false to prevent dead lock.')
    with accelerator.main_process_first():
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForCausalLM.from_pretrained(model_name)
        dataset = ZhihuQADataset()
    tokenizer.add_special_tokens({'pad_token': '<pad>'})
    model.resize_token_embeddings(len(tokenizer))
    data_loader = DataLoader(
        dataset=dataset,
        collate_fn=HFLLMITCollator(
            tokenizer=tokenizer, 
            **CollatorConfig(),
        ).collate_fn,
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
    trainer = HFLLMTrainer(
        model=model, 
        data_loader=data_loader, 
        optimizer=optimizer, 
        logger=logger, 
        accelerator=accelerator,
        tokenizer=tokenizer,
        lr_scheduler=scheduler,
        lr_scheduler_mode='per_step',
        **TrainerConfig(),
    )
    trainer.run()

launch(main, **LaunchConfig())
