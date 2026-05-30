from typing import Dict, List, Optional, Any, Tuple, Callable
from pathlib import Path
import asyncio
import torch
import numpy as np

import logging
from engines.ml.lstm_compute import (
    LSTMConfig,
    LSTMModel,
    create_sequences,
    validate_model,
    predict_signal,
    predict_batch,
    get_model_info,
)

logger = logging.getLogger(__name__)


class LSTMStrategy:
    def __init__(self, config: LSTMConfig):
        from infrastructure.acceleration import device
        self.config = config
        self.model = LSTMModel(config).to(device)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=config.learning_rate)
        self.criterion = torch.nn.MSELoss()

        self._is_trained = False
        self._feature_mean = None
        self._feature_std = None

        if config.model_path and Path(config.model_path).exists():
            self.load(config.model_path)

        logger.info(f"LSTM Strategy initialized on {device}")

    async def train(
        self,
        features: torch.Tensor,
        labels: torch.Tensor,
        val_split: float = 0.2,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> Dict[str, Any]:
        self.model.train()

        from infrastructure.acceleration import to_gpu
        from infrastructure.utilities.progress import ProgressTracker, ProgressType, ProgressBar, get_progress_tracker

        if not isinstance(features, torch.Tensor):
            features = to_gpu(features)
        if not isinstance(labels, torch.Tensor):
            labels = to_gpu(labels)

        if features.dim() == 2:
            features, labels = self._create_sequences(features, labels)
        elif features.dim() != 3:
            features = features.unsqueeze(0)

        self._feature_mean = features.mean(dim=(0, 1), keepdim=True)
        self._feature_std = features.std(dim=(0, 1), keepdim=True) + 1e-8
        features = (features - self._feature_mean) / self._feature_std

        n = len(features)
        n_val = int(n * val_split)
        n_train = n - n_val

        train_features = features[:n_train]
        train_labels = labels[:n_train]
        val_features = features[n_train:]
        val_labels = labels[n_train:]

        train_dataset = torch.utils.data.TensorDataset(train_features, train_labels)
        train_loader = torch.utils.data.DataLoader(
            train_dataset, batch_size=self.config.batch_size, shuffle=True
        )

        tracker = get_progress_tracker()
        task_id = tracker.create_task(
            ProgressType.LSTM_TRAIN,
            total=self.config.epochs,
            message="Training LSTM model",
            metadata={"batch_size": self.config.batch_size, "train_samples": n_train},
        )

        bar = ProgressBar(total=self.config.epochs, desc="LSTM Training")

        if progress_callback:
            progress_callback(0, self.config.epochs, "Starting training")

        best_val_loss = float('inf')
        patience_counter = 0
        train_losses = []
        val_losses = []

        for epoch in range(self.config.epochs):
            self.model.train()
            epoch_loss = 0.0

            for batch_features, batch_labels in train_loader:
                self.optimizer.zero_grad()

                outputs = self.model(batch_features)
                loss = self.criterion(outputs.squeeze(), batch_labels.squeeze())

                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                self.optimizer.step()

                epoch_loss += loss.item()

            avg_train_loss = epoch_loss / len(train_loader)
            train_losses.append(avg_train_loss)

            val_loss = validate_model(self.model, val_features, val_labels, self.criterion)
            val_losses.append(val_loss)

            tracker.update(
                task_id,
                current=epoch + 1,
                message=f"Epoch {epoch+1}: loss={avg_train_loss:.4f}",
            )
            bar.update(1, message=f"loss={avg_train_loss:.4f}, val={val_loss:.4f}")

            if progress_callback:
                progress_callback(epoch + 1, self.config.epochs, f"loss={avg_train_loss:.4f}")

            if (epoch + 1) % 10 == 0:
                logger.info(f"Epoch {epoch+1}/{self.config.epochs}: train_loss={avg_train_loss:.6f}, val_loss={val_loss:.6f}")

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
                if self.config.model_path:
                    self.save(self.config.model_path)
            else:
                patience_counter += 1
                if patience_counter >= self.config.early_stopping_patience:
                    logger.info(f"Early stopping at epoch {epoch+1}")
                    tracker.update(task_id, current=self.config.epochs, message=f"Early stopping at epoch {epoch+1}")
                    break

        self._is_trained = True

        tracker.complete(
            task_id,
            result={
                "epochs": len(train_losses),
                "final_train_loss": train_losses[-1],
                "final_val_loss": val_losses[-1],
                "best_val_loss": best_val_loss,
            },
            message=f"Training completed, best_val_loss={best_val_loss:.4f}",
        )

        return {
            "epochs": len(train_losses),
            "final_train_loss": train_losses[-1],
            "final_val_loss": val_losses[-1],
            "best_val_loss": best_val_loss,
        }

    async def predict(self, features: torch.Tensor) -> int:
        if not self._is_trained:
            logger.warning("Model not trained yet")
            return 0

        return predict_signal(
            self.model, features, self._feature_mean, self._feature_std, self.config
        )

    async def predict_batch(self, features: torch.Tensor) -> torch.Tensor:
        if not self._is_trained:
            raise RuntimeError("Model not trained yet")

        return predict_batch(self.model, features, self._feature_mean, self._feature_std)

    def _create_sequences(
        self,
        features: torch.Tensor,
        labels: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        return create_sequences(
            features, labels,
            self.config.sequence_length,
            self.config.prediction_horizon,
        )

    def save(self, path: str):
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'config': self.config.to_dict(),
            'feature_mean': self._feature_mean,
            'feature_std': self._feature_std,
            'is_trained': self._is_trained,
        }, path)
        logger.info(f"Model saved to {path}")

    def load(self, path: str):
        from infrastructure.acceleration import device
        checkpoint = torch.load(path, map_location=device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        self._feature_mean = checkpoint.get('feature_mean')
        self._feature_std = checkpoint.get('feature_std')
        self._is_trained = checkpoint.get('is_trained', True)
        logger.info(f"Model loaded from {path}")

    def get_model_info(self) -> Dict[str, Any]:
        return get_model_info(self.model, self.config, self._is_trained)


class LSTMStrategyBuilder:
    @staticmethod
    def create_default(input_size: int = 21) -> LSTMStrategy:
        config = LSTMConfig(
            input_size=input_size,
            hidden_size=128,
            num_layers=2,
            dropout=0.2,
            sequence_length=60,
            prediction_horizon=1,
        )
        return LSTMStrategy(config)

    @staticmethod
    def create_fast(input_size: int = 21) -> LSTMStrategy:
        config = LSTMConfig(
            input_size=input_size,
            hidden_size=64,
            num_layers=1,
            dropout=0.1,
            sequence_length=30,
            prediction_horizon=1,
            epochs=50,
            batch_size=128,
        )
        return LSTMStrategy(config)

    @staticmethod
    def create_deep(input_size: int = 21) -> LSTMStrategy:
        config = LSTMConfig(
            input_size=input_size,
            hidden_size=256,
            num_layers=3,
            dropout=0.3,
            bidirectional=True,
            sequence_length=120,
            prediction_horizon=1,
            epochs=200,
            batch_size=32,
        )
        return LSTMStrategy(config)
