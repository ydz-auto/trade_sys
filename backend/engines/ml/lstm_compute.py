from typing import Dict, List, Optional, Any, Tuple

import torch
import numpy as np

import logging

logger = logging.getLogger(__name__)


class LSTMConfig:
    def __init__(
        self,
        input_size: int = 21,
        hidden_size: int = 128,
        num_layers: int = 2,
        dropout: float = 0.2,
        bidirectional: bool = False,
        sequence_length: int = 60,
        prediction_horizon: int = 1,
        learning_rate: float = 0.001,
        batch_size: int = 64,
        epochs: int = 100,
        early_stopping_patience: int = 10,
        threshold_up: float = 0.02,
        threshold_down: float = -0.02,
        model_path: Optional[str] = None,
    ):
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.dropout = dropout
        self.bidirectional = bidirectional
        self.sequence_length = sequence_length
        self.prediction_horizon = prediction_horizon
        self.learning_rate = learning_rate
        self.batch_size = batch_size
        self.epochs = epochs
        self.early_stopping_patience = early_stopping_patience
        self.threshold_up = threshold_up
        self.threshold_down = threshold_down
        self.model_path = model_path

    def to_dict(self) -> Dict[str, Any]:
        return {
            "input_size": self.input_size,
            "hidden_size": self.hidden_size,
            "num_layers": self.num_layers,
            "dropout": self.dropout,
            "bidirectional": self.bidirectional,
            "sequence_length": self.sequence_length,
            "prediction_horizon": self.prediction_horizon,
            "learning_rate": self.learning_rate,
            "batch_size": self.batch_size,
            "epochs": self.epochs,
            "threshold_up": self.threshold_up,
            "threshold_down": self.threshold_down,
        }


class LSTMModel(torch.nn.Module):
    def __init__(self, config: LSTMConfig):
        super().__init__()
        self.config = config
        self.lstm = torch.nn.LSTM(
            input_size=config.input_size,
            hidden_size=config.hidden_size,
            num_layers=config.num_layers,
            batch_first=True,
            dropout=config.dropout if config.num_layers > 1 else 0,
            bidirectional=config.bidirectional,
        )
        lstm_output_size = config.hidden_size * (2 if config.bidirectional else 1)
        self.fc = torch.nn.Sequential(
            torch.nn.Linear(lstm_output_size, 64),
            torch.nn.ReLU(),
            torch.nn.Dropout(config.dropout),
            torch.nn.Linear(64, 32),
            torch.nn.ReLU(),
            torch.nn.Dropout(config.dropout),
            torch.nn.Linear(32, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        lstm_out, _ = self.lstm(x)
        last_output = lstm_out[:, -1, :]
        return self.fc(last_output)


def create_sequences(
    features: torch.Tensor,
    labels: torch.Tensor,
    sequence_length: int,
    prediction_horizon: int,
) -> Tuple[torch.Tensor, torch.Tensor]:
    sequences = []
    sequence_labels = []
    for i in range(sequence_length, len(features) - prediction_horizon):
        seq = features[i - sequence_length:i]
        label = labels[i + prediction_horizon - 1]
        sequences.append(seq)
        sequence_labels.append(label)
    if sequences:
        return torch.stack(sequences), torch.stack(sequence_labels)
    return features.unsqueeze(0), labels


def validate_model(
    model: torch.nn.Module,
    features: torch.Tensor,
    labels: torch.Tensor,
    criterion: torch.nn.Module,
) -> float:
    model.eval()
    with torch.no_grad():
        outputs = model(features)
        loss = criterion(outputs.squeeze(), labels.squeeze())
    return loss.item()


def predict_signal(
    model: torch.nn.Module,
    features: torch.Tensor,
    feature_mean: Optional[torch.Tensor],
    feature_std: Optional[torch.Tensor],
    config: LSTMConfig,
) -> int:
    model.eval()
    if features.dim() == 2:
        if len(features) < config.sequence_length:
            return 0
        features = features[-config.sequence_length:].unsqueeze(0)
    elif features.dim() == 3:
        pass
    else:
        features = features.unsqueeze(0).unsqueeze(0)

    if feature_mean is not None:
        features = (features - feature_mean) / feature_std

    with torch.no_grad():
        prediction = model(features).squeeze()

    pred_value = prediction.item()
    if pred_value > config.threshold_up:
        return 1
    elif pred_value < config.threshold_down:
        return -1
    return 0


def predict_batch(
    model: torch.nn.Module,
    features: torch.Tensor,
    feature_mean: Optional[torch.Tensor],
    feature_std: Optional[torch.Tensor],
) -> torch.Tensor:
    model.eval()
    if feature_mean is not None:
        features = (features - feature_mean) / feature_std
    with torch.no_grad():
        predictions = model(features).squeeze()
    return predictions


def get_model_info(
    model: torch.nn.Module,
    config: LSTMConfig,
    is_trained: bool,
) -> Dict[str, Any]:
    from infrastructure.acceleration import device
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    return {
        "config": config.to_dict(),
        "total_params": total_params,
        "trainable_params": trainable_params,
        "is_trained": is_trained,
        "device": str(device),
    }
