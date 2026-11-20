import torch
import torch.nn as nn
from pathlib import Path


class GlucoRAGTransformer(nn.Module):
    def __init__(self, d_model=128, n_heads=4, num_layers=3, dropout=0.1):
        super().__init__()

        self.input_embed = nn.Linear(1, d_model)

        self.pos_encoder = nn.Parameter(
            torch.randn(1, 24, d_model)
        )

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=n_heads,
            dim_feedforward=d_model * 4,
            dropout=dropout,
            batch_first=True
        )

        self.transformer_encoder = nn.TransformerEncoder(
            encoder_layer,
            num_layers=num_layers
        )

        self.head_30 = nn.Sequential(
            nn.Linear(d_model, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 1)
        )

        self.head_60 = nn.Sequential(
            nn.Linear(d_model, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 1)
        )

    def forward(self, x):
        out = self.input_embed(x) + self.pos_encoder[:, :x.size(1), :]
        out = self.transformer_encoder(out)

        representation = out[:, -1, :]

        pred_30 = self.head_30(representation).squeeze(-1)
        pred_60 = self.head_60(representation).squeeze(-1)

        return pred_30, pred_60


def load_glucorag_model():
    device = torch.device("cpu")

    project_root = Path(__file__).resolve().parents[1]
    checkpoint_path = (
        project_root / "model" / "glucorag_transformer_multidataset.pth"
    )

    if not checkpoint_path.exists():
        raise FileNotFoundError(
            f"Model checkpoint not found: {checkpoint_path}"
        )

    checkpoint = torch.load(
        checkpoint_path,
        map_location=device
    )

    model = GlucoRAGTransformer(
        d_model=checkpoint.get("d_model", 128),
        n_heads=checkpoint.get("n_heads", 4),
        num_layers=checkpoint.get("num_layers", 3)
    )

    model.load_state_dict(
        checkpoint["model_state_dict"],
        strict=True
    )

    model.to(device)
    model.eval()

    return model, device
