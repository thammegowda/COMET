# -*- coding: utf-8 -*-
import os
import shutil
import unittest
import warnings

import torch
from comet.models import ReferencelessRegression
from pytorch_lightning import seed_everything
from pytorch_lightning.trainer.trainer import Trainer
from scipy.stats import pearsonr
from tests.data import DATA_PATH
from torch.utils.data import DataLoader

os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["OMP_NUM_THREADS"] = "1"


class TestReferencelessRegression(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(os.path.join(DATA_PATH, "checkpoints"))

    def test_training(self):

        seed_everything(12)
        trainer = Trainer(
            gpus=0,
            max_epochs=10,
            deterministic=True,
            enable_checkpointing=True,
            default_root_dir=DATA_PATH,
            logger=False,
            enable_progress_bar=False,
        )
        model = ReferencelessRegression(
            encoder_model="BERT",
            pretrained_model="google/bert_uncased_L-2_H-128_A-2",
            train_data=os.path.join(DATA_PATH, "test_regression_data.csv"),
            validation_data=os.path.join(DATA_PATH, "test_regression_data.csv"),
            hidden_sizes=[256],
            layerwise_decay=0.95,
            batch_size=32,
            learning_rate=1e-04,
            encoder_learning_rate=1e-04,
        )
        warnings.filterwarnings(
            "ignore",
            category=UserWarning,
            message=".*Consider increasing the value of the `num_workers` argument` .*",
        )
        trainer.fit(model)
        self.assertTrue(
            os.path.exists(
                os.path.join(DATA_PATH, "checkpoints", "epoch=9-step=159.ckpt")
            )
        )

        saved_model = ReferencelessRegression.load_from_checkpoint(
            os.path.join(DATA_PATH, "checkpoints", "epoch=9-step=159.ckpt")
        )
        dataset = saved_model.read_csv(
            os.path.join(DATA_PATH, "test_regression_data.csv")
        )
        y = [s["score"] for s in dataset]
        dataloader = DataLoader(
            dataset=dataset,
            batch_size=256,
            collate_fn=lambda x: saved_model.prepare_sample(x, inference=True),
            num_workers=2,
        )
        y_hat = (
            torch.cat(
                trainer.predict(
                    ckpt_path="best", dataloaders=dataloader, return_predictions=True
                ),
                dim=0,
            )
            .cpu()
            .tolist()
        )
        self.assertAlmostEqual(pearsonr(y_hat, y)[0], 0.8, places=1)
